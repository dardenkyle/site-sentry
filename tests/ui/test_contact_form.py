"""Contact form tests for kyledarden.com.

The form must post to FormSubmit's ajax endpoint and surface failures:
posting to the plain endpoint (or ignoring the response body) silently
drops messages, which is exactly what dardenkyle/portfolio-site#82
shipped for weeks. Every request toward formsubmit.co is intercepted
and fulfilled with a mocked response, so these tests never send email.
"""

import pytest
from playwright.sync_api import Page, Request, Route, expect

from tests.utils.logger import get_logger

logger = get_logger(__name__)

# Intercept everything sent toward FormSubmit, whatever the path, so a
# regression to a non-ajax endpoint is captured instead of escaping
FORMSUBMIT_URL_PATTERN = "https://formsubmit.co/**"

# The only endpoint that processes programmatic (fetch) submissions
FORMSUBMIT_AJAX_PREFIX = "https://formsubmit.co/ajax/"

# FormSubmit reports both outcomes as HTTP 200; the body is the signal
SUCCESS_BODY = '{"success": "true", "message": "The form was submitted successfully."}'
FAILURE_BODY = '{"success": "false", "message": "Simulated FormSubmit failure"}'

SUCCESS_BANNER_TEXT = "Message sent successfully"
FAILURE_MESSAGE_TEXT = "Failed to send message"

TEST_NAME = "Site Sentry"
TEST_EMAIL = "site-sentry@example.com"
TEST_MESSAGE = "Automated contact form check - no email is sent."


def _submit_contact_form(page: Page, response_body: str) -> list[Request]:
    """Fill and submit the contact form with FormSubmit fully mocked.

    Args:
        page: Playwright page to drive
        response_body: JSON body the mocked FormSubmit returns

    Returns:
        The requests the form sent toward formsubmit.co
    """
    captured: list[Request] = []

    def fulfill(route: Route) -> None:
        captured.append(route.request)
        route.fulfill(status=200, content_type="application/json", body=response_body)

    page.route(FORMSUBMIT_URL_PATTERN, fulfill)
    page.goto("/contact")
    page.fill("#name", TEST_NAME)
    page.fill("#email", TEST_EMAIL)
    page.fill("#message", TEST_MESSAGE)
    page.get_by_role("button", name="Send Message").click()
    return captured


@pytest.mark.ui
def test_contact_form_targets_formsubmit_ajax(page: Page) -> None:
    """Test that submitting sends one POST to the FormSubmit ajax endpoint.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing contact form submission wiring")

    requests = _submit_contact_form(page, SUCCESS_BODY)

    expect(page.get_by_text(SUCCESS_BANNER_TEXT)).to_be_visible()

    assert len(requests) == 1, f"Expected exactly one FormSubmit request, saw {len(requests)}"
    request = requests[0]
    assert request.method == "POST", f"Expected POST, got {request.method}"
    assert request.url.startswith(FORMSUBMIT_AJAX_PREFIX), (
        f"Form posted to {request.url}; fetch submissions are only "
        "processed on the /ajax/ endpoint (portfolio-site#82)"
    )

    post_data = request.post_data or ""
    for value in (TEST_NAME, TEST_EMAIL, TEST_MESSAGE):
        assert value in post_data, f"Submitted payload is missing {value!r}"

    logger.info("Contact form posts the payload to %s", request.url)


@pytest.mark.ui
def test_contact_form_surfaces_failure(page: Page) -> None:
    """Test that a FormSubmit failure is shown to the user, not masked.

    Canary for the response check: FormSubmit reports failures as
    HTTP 200 with success "false", the exact shape that used to render
    as false success in portfolio-site#82.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing that contact form failures are surfaced")

    _submit_contact_form(page, FAILURE_BODY)

    expect(page.get_by_text(FAILURE_MESSAGE_TEXT)).to_be_visible()
    expect(page.get_by_text(SUCCESS_BANNER_TEXT)).not_to_be_visible()

    logger.info("Contact form correctly surfaced the mocked failure")
