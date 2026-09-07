from __future__ import annotations

import inspect
import json
import os
import threading
import tomllib
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import pytest
from http.server import ThreadingHTTPServer

import kora.studio_drawer_render as studio_drawer_render
import kora.studio_harness_display_render as studio_harness_display_render
import kora.studio_harness_request_render as studio_harness_request_render
import kora.studio_legacy_render as studio_legacy_render
import kora.studio_model_runtime_render as studio_model_runtime_render
import kora.studio_reference_render as studio_reference_render
import kora.studio_run_state_render as studio_run_state_render
import kora.studio_script_render as studio_script_render
import kora.studio_selected_run_render as studio_selected_run_render
import kora.studio_server as studio_server
import kora.studio_shell_render as studio_shell_render
import kora.studio_status_boundary_render as studio_status_boundary_render
import kora.studio_style_render as studio_style_render
from kora.studio_drawer_render import render_right_details_drawer
from kora.studio_server import (
    DEFAULT_STUDIO_HOST,
    DEFAULT_STUDIO_PORT,
    STUDIO_LOCAL_PREVIEW_CSP,
    create_studio_request_handler,
    get_studio_asset_path_status,
    get_studio_css_asset_path_status,
    get_studio_url,
    get_studio_health_payload,
    get_studio_server_status,
    get_studio_status_payload,
    is_allowed_studio_host,
    open_studio_browser,
    render_studio_placeholder_html,
    render_studio_server_status_text,
    run_studio_server,
)
from kora.studio_harness_runs import clear_local_harness_run_records
from kora.studio_harness_request_render import (
    render_local_harness_request_selector_panels,
    render_local_harness_selector_item,
    render_local_harness_trigger_item,
    render_local_harness_trigger_reference_panels,
)
from kora.studio_harness_display_render import (
    render_execution_viewer_section,
    render_local_harness_preview_section,
    render_report_viewer_placeholder_section,
    render_standard_vs_kora_section,
)
from kora.studio_model_runtime_render import (
    render_catalog_installed_section,
    render_disabled_actions_section,
    render_model_capability_section,
    render_model_selector_option,
    render_runtime_status_section,
    render_setup_guidance_section,
    render_system_profile_section,
)
from kora.studio_reference_render import render_reference_panels
from kora.studio_legacy_render import render_legacy_preview_opening
from kora.studio_run_state_render import (
    render_local_run_history_panels,
    render_retry_error_state_panels,
    render_run_state_history_panels,
)
from kora.studio_selected_run_render import render_selected_run_panels, render_selected_run_summary_panel
from kora.studio_shell_render import render_shell_layout
from kora.studio_script_render import (
    STUDIO_JAVASCRIPT_SOURCE_PACKAGE,
    STUDIO_JAVASCRIPT_SOURCE_PATH,
    render_studio_javascript,
)
from kora.studio_status_boundary_render import (
    render_kora_boost_boundary_section,
    render_launch_local_status_section,
    render_shell_boundary_strip,
)
from kora.studio_style_render import STUDIO_CSS_SOURCE_PACKAGE, STUDIO_CSS_SOURCE_PATH, render_studio_css

APPROVED_BOOST_MESSAGE = "Less waiting. Better answers. No hardware upgrade."
TECHNICAL_EXPLANATION = (
    "KORA Boost handles simple work through fast paths and saves model power "
    "for the tasks that need it."
)
EXPECTED_STUDIO_STYLESHEETS = ["/studio-assets/studio.css"]
EXPECTED_STUDIO_SCRIPT = {"src": "/studio-assets/studio.js"}
EXPECTED_APPROVED_REQUEST_JSON_SCRIPT = {
    "type": "application/json",
    "id": "kora-approved-requests-data",
}
ALLOWED_STUDIO_ASSET_URLS = {"/studio-assets/studio.css", "/studio-assets/studio.js"}
FORBIDDEN_HTML_RESOURCE_PREFIXES = {
    "data:": "data URL resource",
    "blob:": "blob URL resource",
    "http://": "remote resource URL",
    "https://": "remote resource URL",
    "javascript:": "javascript pseudo URL",
    "//": "remote resource URL",
}
EXPECTED_STUDIO_CSP_DIRECTIVES = {
    "default-src": ["'none'"],
    "base-uri": ["'none'"],
    "object-src": ["'none'"],
    "frame-ancestors": ["'none'"],
    "form-action": ["'none'"],
    "style-src": ["'self'"],
    "script-src": ["'self'"],
    "connect-src": ["'self'"],
}
CSP_FORBIDDEN_SOURCES = {
    "*": "wildcard CSP source",
    "data:": "data CSP source",
    "blob:": "blob CSP source",
    "http:": "HTTP CSP source",
    "https:": "HTTP CSP source",
    "http://*": "HTTP CSP source",
    "https://*": "HTTP CSP source",
    "'unsafe-inline'": "unsafe-inline",
    "'unsafe-eval'": "unsafe-eval",
}
CSP_NEW_RESOURCE_DIRECTIVES_REQUIRING_REVIEW = ("img-src", "font-src", "media-src", "worker-src", "frame-src")
CSS_FORBIDDEN_PATTERNS = (
    ("@import", "CSS @import"),
    ("url(", "CSS url"),
    ("data:", "data URL resource"),
    ("blob:", "blob URL resource"),
    ("http://", "remote resource URL"),
    ("https://", "remote resource URL"),
    ("//cdn.", "remote resource URL"),
)
PACKAGE_ASSET_FORBIDDEN_TOKENS = (
    "unsafe-inline",
    "unsafe-eval",
    "data:",
    "blob:",
    "http://",
    "https://",
    "//cdn.",
    "cdn.jsdelivr",
    "unpkg.com",
)

RENDER_HELPER_FUNCTIONS = [
    studio_shell_render.render_shell_layout,
    studio_drawer_render.render_right_details_drawer,
    studio_selected_run_render.render_selected_run_summary_panel,
    studio_selected_run_render.render_selected_run_state_panel,
    studio_selected_run_render.render_selected_run_detail_panels,
    studio_selected_run_render.render_selected_run_panels,
    studio_harness_display_render.render_local_harness_preview_section,
    studio_harness_display_render.render_execution_viewer_section,
    studio_harness_display_render.render_standard_vs_kora_section,
    studio_harness_display_render.render_report_viewer_placeholder_section,
    studio_harness_request_render.render_local_harness_selector_item,
    studio_harness_request_render.render_local_harness_trigger_item,
    studio_harness_request_render.render_local_harness_request_selector_panels,
    studio_harness_request_render.render_local_harness_trigger_reference_panels,
    studio_legacy_render.render_legacy_preview_opening,
    studio_model_runtime_render.render_model_selector_option,
    studio_model_runtime_render.render_system_profile_section,
    studio_model_runtime_render.render_model_capability_section,
    studio_model_runtime_render.render_runtime_status_section,
    studio_model_runtime_render.render_catalog_installed_section,
    studio_model_runtime_render.render_setup_guidance_section,
    studio_model_runtime_render.render_disabled_actions_section,
    studio_run_state_render.render_retry_error_state_panels,
    studio_run_state_render.render_local_run_history_panels,
    studio_run_state_render.render_run_state_history_panels,
    studio_reference_render.render_endpoint_panel,
    studio_reference_render.render_limitations_panel,
    studio_reference_render.render_local_references_panel,
    studio_reference_render.render_reference_panels,
    studio_status_boundary_render.render_shell_boundary_strip,
    studio_status_boundary_render.render_launch_local_status_section,
    studio_status_boundary_render.render_kora_boost_boundary_section,
    studio_style_render.render_studio_css,
    studio_script_render.render_studio_javascript,
]

RENDER_HELPER_MODULES = [
    studio_shell_render,
    studio_drawer_render,
    studio_selected_run_render,
    studio_harness_display_render,
    studio_harness_request_render,
    studio_legacy_render,
    studio_model_runtime_render,
    studio_run_state_render,
    studio_reference_render,
    studio_status_boundary_render,
    studio_style_render,
    studio_script_render,
]

EXPECTED_RENDER_HELPER_NAMES = {
    "kora.studio_shell_render.render_shell_layout",
    "kora.studio_drawer_render.render_right_details_drawer",
    "kora.studio_selected_run_render.render_selected_run_summary_panel",
    "kora.studio_selected_run_render.render_selected_run_state_panel",
    "kora.studio_selected_run_render.render_selected_run_detail_panels",
    "kora.studio_selected_run_render.render_selected_run_panels",
    "kora.studio_harness_display_render.render_local_harness_preview_section",
    "kora.studio_harness_display_render.render_execution_viewer_section",
    "kora.studio_harness_display_render.render_standard_vs_kora_section",
    "kora.studio_harness_display_render.render_report_viewer_placeholder_section",
    "kora.studio_harness_request_render.render_local_harness_selector_item",
    "kora.studio_harness_request_render.render_local_harness_trigger_item",
    "kora.studio_harness_request_render.render_local_harness_request_selector_panels",
    "kora.studio_harness_request_render.render_local_harness_trigger_reference_panels",
    "kora.studio_legacy_render.render_legacy_preview_opening",
    "kora.studio_model_runtime_render.render_model_selector_option",
    "kora.studio_model_runtime_render.render_system_profile_section",
    "kora.studio_model_runtime_render.render_model_capability_section",
    "kora.studio_model_runtime_render.render_runtime_status_section",
    "kora.studio_model_runtime_render.render_catalog_installed_section",
    "kora.studio_model_runtime_render.render_setup_guidance_section",
    "kora.studio_model_runtime_render.render_disabled_actions_section",
    "kora.studio_run_state_render.render_retry_error_state_panels",
    "kora.studio_run_state_render.render_local_run_history_panels",
    "kora.studio_run_state_render.render_run_state_history_panels",
    "kora.studio_reference_render.render_endpoint_panel",
    "kora.studio_reference_render.render_limitations_panel",
    "kora.studio_reference_render.render_local_references_panel",
    "kora.studio_reference_render.render_reference_panels",
    "kora.studio_status_boundary_render.render_shell_boundary_strip",
    "kora.studio_status_boundary_render.render_launch_local_status_section",
    "kora.studio_status_boundary_render.render_kora_boost_boundary_section",
    "kora.studio_style_render.render_studio_css",
    "kora.studio_script_render.render_studio_javascript",
}


class StudioHtmlResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.scripts: list[dict[str, str]] = []
        self.resource_urls: list[tuple[str, str, str]] = []
        self.inline_style_attributes: list[tuple[str, str]] = []
        self.inline_event_handler_attributes: list[tuple[str, str, str]] = []
        self.style_elements: list[dict[str, str]] = []
        self.meta_refresh_values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_tag(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_tag(tag, attrs)

    def _record_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalised_tag = tag.lower()
        attr_map = {name.lower(): value or "" for name, value in attrs}
        self.tags.append((normalised_tag, attr_map))
        if normalised_tag == "script":
            self.scripts.append(attr_map)
        if normalised_tag == "style":
            self.style_elements.append(attr_map)
        if normalised_tag == "meta" and attr_map.get("http-equiv", "").lower() == "refresh":
            self.meta_refresh_values.append(attr_map.get("content", ""))
        if "style" in attr_map:
            self.inline_style_attributes.append((normalised_tag, attr_map["style"]))
        for attr_name, attr_value in attr_map.items():
            if attr_name.startswith("on"):
                self.inline_event_handler_attributes.append((normalised_tag, attr_name, attr_value))
        for attr_name in ("src", "href", "action", "formaction", "poster", "data", "srcset"):
            if attr_name in attr_map:
                self.resource_urls.append((normalised_tag, attr_name, attr_map[attr_name]))


def _qualified_name(function: object) -> str:
    assert hasattr(function, "__module__")
    assert hasattr(function, "__name__")
    return f"{function.__module__}.{function.__name__}"


def _parse_csp_directives(csp: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for directive in csp.split(";"):
        parts = directive.strip().split()
        if parts:
            directives[parts[0]] = parts[1:]
    return directives


def _parse_studio_html_resources(html: str) -> StudioHtmlResourceParser:
    parser = StudioHtmlResourceParser()
    parser.feed(html)
    return parser


def _stylesheet_hrefs(parser: StudioHtmlResourceParser) -> list[str]:
    return [
        attrs["href"]
        for tag, attrs in parser.tags
        if tag == "link" and attrs.get("rel") == "stylesheet"
    ]


def _script_groups(parser: StudioHtmlResourceParser) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return (
        [attrs for attrs in parser.scripts if "src" in attrs],
        [attrs for attrs in parser.scripts if "src" not in attrs],
    )


def _normalise_resource_url(url: str) -> str:
    return url.strip().lower()


def _resource_url_candidates(attr_name: str, url: str) -> list[str]:
    if attr_name == "srcset":
        candidates: list[str] = []
        for item in url.split(","):
            parts = item.strip().split()
            if parts:
                candidates.append(parts[0])
        return candidates
    return [url]


def _meta_refresh_url_candidates(content: str) -> list[str]:
    lowered = content.lower()
    if "url=" not in lowered:
        return []
    return [content[lowered.index("url=") + len("url=") :].strip()]


def _find_studio_html_resource_policy_violations(html: str) -> list[str]:
    parser = _parse_studio_html_resources(html)
    violations: list[str] = []

    if parser.inline_style_attributes:
        violations.append("inline style attribute")
    if parser.inline_event_handler_attributes:
        violations.append("inline event handler")
    if parser.style_elements:
        violations.append("inline style block")

    if _stylesheet_hrefs(parser) != EXPECTED_STUDIO_STYLESHEETS:
        violations.append("stylesheet must be /studio-assets/studio.css")

    src_scripts, inline_scripts = _script_groups(parser)
    if src_scripts != [EXPECTED_STUDIO_SCRIPT]:
        violations.append("executable script must be /studio-assets/studio.js")
    if inline_scripts != [EXPECTED_APPROVED_REQUEST_JSON_SCRIPT]:
        violations.append("inline script must be approved request JSON")

    resource_urls = parser.resource_urls + [
        ("meta", "refresh", url)
        for refresh_value in parser.meta_refresh_values
        for url in _meta_refresh_url_candidates(refresh_value)
    ]
    for _tag, attr_name, url in resource_urls:
        for candidate in _resource_url_candidates(attr_name, url):
            normalised_url = _normalise_resource_url(candidate)
            for prefix, violation in FORBIDDEN_HTML_RESOURCE_PREFIXES.items():
                if normalised_url.startswith(prefix):
                    violations.append(violation)
            if normalised_url.startswith("/studio-assets/") and candidate.strip() not in ALLOWED_STUDIO_ASSET_URLS:
                violations.append("unapproved studio asset")

    return violations


def _find_csp_source_policy_violations(csp: str) -> list[str]:
    directives = _parse_csp_directives(csp)
    violations: list[str] = []
    for sources in directives.values():
        for source in sources:
            if source in CSP_FORBIDDEN_SOURCES:
                violations.append(CSP_FORBIDDEN_SOURCES[source])
            if "://" in source:
                violations.append("external CSP host")
    for directive in CSP_NEW_RESOURCE_DIRECTIVES_REQUIRING_REVIEW:
        if directive in directives:
            violations.append(f"new resource directive {directive}")
    return violations


def _find_css_resource_policy_violations(css: str) -> list[str]:
    lowered = css.lower()
    violations: list[str] = []
    for token, violation in CSS_FORBIDDEN_PATTERNS:
        if token in lowered:
            violations.append(violation)
    return violations


def test_render_helper_api_contracts_are_string_only_and_keyword_stable() -> None:
    for helper in RENDER_HELPER_FUNCTIONS:
        signature = inspect.signature(helper)
        assert signature.return_annotation in (str, "str")
        for parameter in signature.parameters.values():
            assert parameter.annotation in (str, int, "str", "int")
            assert parameter.default is inspect.Parameter.empty
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_render_helper_contract_covers_all_public_render_functions() -> None:
    contracted_helpers = {_qualified_name(helper) for helper in RENDER_HELPER_FUNCTIONS}
    discovered_helpers = {
        f"{module.__name__}.{name}"
        for module in RENDER_HELPER_MODULES
        for name, value in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("render_") and value.__module__ == module.__name__
    }

    assert contracted_helpers == EXPECTED_RENDER_HELPER_NAMES
    assert discovered_helpers == EXPECTED_RENDER_HELPER_NAMES


def test_render_helper_modules_do_not_import_io_network_or_subprocess_dependencies() -> None:
    forbidden_tokens = [
        "import os",
        "import pathlib",
        "from pathlib",
        "import subprocess",
        "import requests",
        "urllib",
        "webbrowser",
        "open(",
        "Path(",
        "ThreadingHTTPServer",
        "BaseHTTPRequestHandler",
    ]

    for module in RENDER_HELPER_MODULES:
        source = inspect.getsource(module)
        for token in forbidden_tokens:
            assert token not in source, f"{module.__name__} must stay render-only; found {token!r}"


def test_render_helper_modules_do_not_own_server_or_payload_assembly() -> None:
    forbidden_tokens = [
        "studio_server",
        "get_studio_server_status",
        "create_studio_request_handler",
        "BaseHTTPRequestHandler",
        "ThreadingHTTPServer",
        "send_response",
        "send_header",
        "end_headers",
        "wfile",
        "rfile",
        "do_GET",
        "do_POST",
        "trigger_local_harness_run",
        "get_local_harness_run_record",
        "get_local_harness_run_events",
        "format_local_harness_sse",
        "json.dumps",
        "json.loads",
        "html.escape",
    ]

    for module in RENDER_HELPER_MODULES:
        source = inspect.getsource(module)
        for token in forbidden_tokens:
            assert token not in source, f"{module.__name__} must not own server/data assembly; found {token!r}"


def test_server_retains_endpoint_status_escaping_and_document_assembly() -> None:
    server_source = inspect.getsource(studio_server)
    placeholder_source = inspect.getsource(render_studio_placeholder_html)
    handler_source = inspect.getsource(create_studio_request_handler)

    assert "def get_studio_server_status" in server_source
    assert "html.escape" in placeholder_source
    assert "json.dumps(local_harness_requests" in placeholder_source
    assert "<!doctype html>" in placeholder_source
    assert "STUDIO_CSS_ASSET_PATH" in placeholder_source
    assert "render_studio_css" in handler_source
    assert "render_studio_javascript" in handler_source
    assert 'id=\\"kora-approved-requests-data\\"' in placeholder_source
    assert "def do_GET" in handler_source
    assert "def do_POST" in handler_source
    assert "trigger_local_harness_run" in handler_source
    assert "format_local_harness_sse" in handler_source


def test_rendered_preview_preserves_helper_owned_component_markers() -> None:
    html = render_studio_placeholder_html(get_studio_server_status())
    helper_owned_markers = {
        "shell-layout": "kora.studio_shell_render",
        "left-rail": "kora.studio_shell_render",
        "top-model-selector": "kora.studio_shell_render",
        "primary-workflow-band": "kora.studio_server",
        "run-progress-summary": "kora.studio_server",
        "shell-retry-action": "kora.studio_server",
        "primary-result-summary": "kora.studio_server",
        "right-details-drawer": "kora.studio_drawer_render",
        "selected-run-summary": "kora.studio_selected_run_render",
        "generated-event-stream-status": "kora.studio_selected_run_render",
        "selected-run-event-timeline": "kora.studio_selected_run_render",
        "selected-run-counters": "kora.studio_selected_run_render",
        "selected-run-comparison": "kora.studio_selected_run_render",
        "selected-run-report-metadata": "kora.studio_selected_run_render",
        "approved-request-selector": "kora.studio_harness_request_render",
        "retry-error-state": "kora.studio_run_state_render",
        "run-history": "kora.studio_run_state_render",
        "legacy-compatibility-reference": "kora.studio_legacy_render",
        "boundary-strip": "kora.studio_status_boundary_render",
    }

    for marker, owner in helper_owned_markers.items():
        assert f'data-kora-component="{marker}"' in html, f"{marker} missing from rendered preview; owner {owner}"


def test_shell_layout_render_helper_preserves_shell_markers() -> None:
    html = render_shell_layout(
        local_candidate_name="Example mini local model",
        local_candidate_id="example-mini-local",
        local_candidate_type="physically_runnable_local_candidate",
        local_candidate_memory="4",
        local_candidate_installed="false",
        model_selector_count=1,
        model_selector_items="<div>model option</div>",
        composer_html='<section data-kora-component="composer">composer slot</section>',
        details_drawer_html='<aside data-kora-component="right-details-drawer">drawer slot</aside>',
        legacy_preview_html='<details data-kora-component="legacy-compatibility-reference"></details>',
    )

    assert 'data-kora-component="shell-layout"' in html
    assert 'data-kora-component="left-rail"' in html
    assert 'data-kora-component="top-model-selector"' in html
    assert 'data-kora-final-ui-shell="true"' in html
    assert 'data-kora-v1-1-shell-only-hardening="active"' in html
    assert 'data-kora-model-selection-state="catalog-estimate-only"' in html
    assert 'data-kora-component="composer"' in html
    assert 'data-kora-component="right-details-drawer"' in html
    assert 'data-kora-component="legacy-compatibility-reference"' in html
    assert "Selection does not install, download, or execute this model." in html


def test_right_details_drawer_render_helper_preserves_drawer_markers() -> None:
    html = render_right_details_drawer(
        runtime_name="local runtime",
        runtime_detected="false",
        service_status="not connected",
        local_candidate_name="Example mini local model",
        catalog_status="static",
        installed_status="not scanned",
        installed_count="0",
        sample_request_id="faq_lookup_v1",
        sample_route="structured_lookup",
        sample_validation="passed",
        total_requests="1",
        baseline_model_calls="1",
        kora_model_calls="0",
        avoided_model_calls="1",
        report_viewer_status="preview",
        report_source="local_harness_summary",
        report_file_export_enabled="false",
        report_file_written="false",
    )

    assert 'data-kora-component="right-details-drawer"' in html
    assert 'data-kora-mobile-drawer="right-overlay"' in html
    assert 'data-kora-drawer-section="runtime-status"' in html
    assert 'data-kora-drawer-section="selected-model"' in html
    assert 'data-kora-drawer-section="catalog-vs-installed"' in html
    assert 'data-kora-drawer-section="route-trace"' in html
    assert 'data-kora-drawer-section="generated-counters"' in html
    assert 'data-kora-drawer-section="selected-run-surfaces"' in html
    assert 'data-kora-drawer-section="report-metadata"' in html
    assert 'data-kora-drawer-section="claim-boundaries"' in html
    assert 'data-kora-drawer-selected-run-coverage="timeline,counters,comparison,report-metadata"' in html
    assert 'data-kora-v1-1-drawer-selected-run-polish="primary-diagnostics"' in html
    assert 'data-kora-drawer-boundary-coverage="provider,cloud,download,model-execution,report-export,private-scan,runtime-list"' in html
    assert 'id="kora-drawer-selected-run-id"' in html
    assert "Drawer selected-run diagnostics mirror shell state for normal inspection" in html
    assert "Generated harness events only." in html
    assert "No arbitrary prompt execution." in html
    assert "No model execution." in html
    assert "No provider calls." in html
    assert "No downloads." in html
    assert "No report file export or writing." in html
    assert "No private model directory scanning." in html
    assert "No runtime model list commands." in html


def test_selected_run_render_helpers_preserve_selected_run_markers() -> None:
    summary_html = render_selected_run_summary_panel(selector_preview_id="faq_lookup_v1")
    panels_html = render_selected_run_panels()
    html = f"{summary_html}\n{panels_html}"

    assert 'data-kora-component="selected-run-summary"' in html
    assert 'id="kora-composer-selected-run-summary"' in html
    assert 'id="kora-composer-request-id">faq_lookup_v1</code>' in html
    assert 'id="kora-selected-run-state"' in html
    assert 'data-kora-component="generated-event-stream-status"' in html
    assert 'data-kora-component="selected-run-event-timeline"' in html
    assert 'data-kora-component="selected-run-counters"' in html
    assert 'data-kora-component="selected-run-comparison"' in html
    assert 'data-kora-component="selected-run-report-metadata"' in html
    assert 'id="kora-selected-run-events"' in html
    assert 'id="kora-selected-run-counters"' in html
    assert 'id="kora-selected-run-comparison"' in html
    assert 'id="kora-selected-run-report-metadata"' in html
    assert "Generated local harness output only" in html
    assert "Not model token streaming" in html
    assert "No provider streaming" in html
    assert "No model execution" in html
    assert "No provider calls" in html
    assert "No downloads" in html
    assert "Not production telemetry" in html
    assert "not production cost evidence" in html
    assert "Report metadata preview only" in html
    assert "No file export" in html
    assert "No file writing" in html


def test_harness_display_render_helpers_preserve_local_harness_boundaries() -> None:
    harness_html = render_local_harness_preview_section(
        local_harness_status_text="local_deterministic_harness_available",
        local_harness_event_source="generated_events_available",
        local_harness_run_trigger="api_endpoint_connected",
        local_harness_request_count="5",
        sample_request_id="local-harness-json-required-fields-001",
        sample_input="Validate required JSON fields.",
        sample_family="json_validation",
        sample_route="deterministic_code",
        sample_validation="passed",
        sample_model_needed="False",
        local_harness_boundary="Local deterministic harness only.",
        request_selector_html='<div data-kora-component="approved-request-selector">selector slot</div>',
        selected_run_state_html='<div id="kora-selected-run-state">state slot</div>',
        run_state_history_html='<div data-kora-component="run-history">history slot</div>',
        selected_run_detail_panels_html='<div data-kora-component="selected-run-event-timeline">details slot</div>',
        trigger_reference_html="<div>trigger slot</div>",
        local_harness_request_items="<li>request slot</li>",
        local_harness_event_items="<li>event slot</li>",
        local_harness_timeline_items="<div>timeline slot</div>",
        local_harness_counter_items="<div>counter slot</div>",
    )
    execution_html = render_execution_viewer_section(
        execution_status="fixture_loaded",
        execution_schema_count="8",
        execution_event_count="6",
        execution_boundary="Fixture boundary.",
        execution_event_items="<li>execution slot</li>",
    )
    comparison_html = render_standard_vs_kora_section(
        standard_vs_kora_status="local_deterministic_harness_generated",
        standard_route_summary="Baseline counts one model call.",
        kora_route_summary="KORA path avoids model call.",
        standard_vs_kora_boundary="Local harness comparison only.",
        standard_vs_kora_metric_items="<div>metric slot</div>",
    )
    report_html = render_report_viewer_placeholder_section(
        report_viewer_status="metadata_preview_connected",
        report_title="Local Harness Summary",
        report_source="local_harness_summary",
        report_sample_run_id="run-001",
        report_sample_request_id="local-harness-json-required-fields-001",
        report_event_count="6",
        report_comparison_status="available",
        report_export_status="disabled",
        report_export_label="Export not connected yet",
        report_file_export_enabled="disabled",
        report_file_written="false",
        report_export_reason="No file export is connected.",
        report_export_boundary="No file writing.",
        report_boundary="Local deterministic harness output only.",
        report_path_display="not written",
        report_fixture_path="docs/kora-studio/fixtures/report.sample.json",
        report_sections="<li>Report section slot</li>",
        report_warnings="<li>Boundary warning slot</li>",
        report_counter_items="<div>report counter slot</div>",
    )
    html = "\n".join([harness_html, execution_html, comparison_html, report_html])

    assert "<h2>Local Harness Preview</h2>" in harness_html
    assert "Harness status" in harness_html
    assert "Sample request" in harness_html
    assert "Model-needed boundaries do not execute models in this milestone" in harness_html
    assert "No provider call, download, or cloud sync is connected" in harness_html
    assert "Generated Event Timeline" in harness_html
    assert "Not model token streaming" in harness_html
    assert "No model execution" in harness_html
    assert "No provider output" in harness_html
    assert "Generated Counters" in harness_html
    assert "No cost or energy conversion is performed" in harness_html
    assert "selector slot" in harness_html
    assert "timeline slot" in harness_html
    assert "counter slot" in harness_html

    assert "<h2>Execution Viewer</h2>" in execution_html
    assert "Fixture/mock events only" in execution_html
    assert "No real model execution" in execution_html
    assert "No provider calls" in execution_html
    assert "No model downloads" in execution_html
    assert "Request received" in execution_html
    assert "Deterministic route check" in execution_html
    assert "Structured lookup and validation pass" in execution_html
    assert "Model fallback skipped / Final counters" in execution_html

    assert "<h2>Standard Mode vs KORA Boost</h2>" in comparison_html
    assert "Local deterministic harness comparison" in comparison_html
    assert "This is not production cost evidence" in comparison_html
    assert "This does not execute a model" in comparison_html
    assert "No cost or energy claim is made" in comparison_html
    assert "metric slot" in comparison_html

    assert "<h2>Report Viewer Placeholder</h2>" in report_html
    assert "Report metadata preview only" in report_html
    assert "No file export in this preview" in report_html
    assert "Not production evidence" in report_html
    assert "No model execution" in report_html
    assert "No provider calls" in report_html
    assert "No cloud sync" in report_html
    assert "No arbitrary local file scan is performed" in report_html
    assert "Report section slot" in report_html
    assert "report counter slot" in report_html

    assert "<script" not in html.lower()
    assert "https://" not in html
    assert "fetch(" not in html


def test_reference_render_helper_preserves_static_local_boundaries() -> None:
    html = render_reference_panels(
        docs_path="/tmp/kora-docs",
        fixtures_path="/tmp/kora-fixtures",
    )

    assert "<h2>Endpoint Panel</h2>" in html
    assert '<a href="/health">/health</a>' in html
    assert '<a href="/status">/status</a>' in html
    assert "/api/harness/run" in html
    assert "/api/harness/events?run_id=&lt;id&gt;" in html
    assert "/api/harness/sse?run_id=&lt;id&gt;" in html
    assert "Arbitrary prompt execution is not connected." in html
    assert "No persistence, provider call, download, or model execution is connected." in html
    assert "It streams no model tokens, provider output, or model output." in html
    assert "<h2>Limitations Panel</h2>" in html
    assert "No provider calls" in html
    assert "No model/runtime integration yet" in html
    assert "No production/API-cost/energy claims" in html
    assert "No claim that KORA removes model memory requirements" in html
    assert "<h2>Local References</h2>" in html
    assert "<code>/tmp/kora-docs</code>" in html
    assert "<code>/tmp/kora-fixtures</code>" in html
    assert "<script" not in html.lower()
    assert "https://" not in html
    assert "fetch(" not in html


def test_status_boundary_render_helpers_preserve_local_only_boundaries() -> None:
    shell_boundary_html = render_shell_boundary_strip()
    launch_html = render_launch_local_status_section(
        section_order_items="<li>Launch/local-only status</li><li>Your Computer</li>",
    )
    boost_html = render_kora_boost_boundary_section()
    html = f"{shell_boundary_html}\n{launch_html}\n{boost_html}"

    assert 'data-kora-component="boundary-strip"' in shell_boundary_html
    assert 'data-kora-shell-local-only-boundary="v1.0"' in shell_boundary_html
    assert 'data-kora-shell-boundary-coverage="provider,cloud,download,model-execution,report-export"' in shell_boundary_html
    assert "Local preview only" in shell_boundary_html
    assert "Provider calls disabled" in shell_boundary_html
    assert "Cloud sync disabled" in shell_boundary_html
    assert "Downloads disabled" in shell_boundary_html
    assert "Model execution not connected yet" in shell_boundary_html
    assert "Report export disabled" in shell_boundary_html
    assert "No arbitrary prompt execution" in shell_boundary_html
    assert "no report file export or writing" in shell_boundary_html

    assert 'aria-label="Launch Local-only Status"' in launch_html
    assert "<h2>Launch / Local-only Status</h2>" in launch_html
    assert "Server: local" in launch_html
    assert "No remote provider requests are made" in launch_html
    assert "No cloud sync is performed" in launch_html
    assert "Model/runtime integration: not connected" in launch_html
    assert "No Ollama model calls happen here" in launch_html
    assert "Launch/local-only status" in launch_html

    assert "<h2>KORA Boost Boundary</h2>" in boost_html
    assert "Standard Mode sends every step to the model" in boost_html
    assert "KORA Boost routes deterministic and structured tasks to CPU/local fast paths first" in boost_html
    assert "KORA does not remove model memory requirements" in boost_html
    assert "Provider/cloud routes are disabled by default" in boost_html

    assert "<script" not in html.lower()
    assert "https://" not in html
    assert "fetch(" not in html


def test_model_runtime_render_helpers_preserve_catalog_and_runtime_boundaries() -> None:
    model_option = render_model_selector_option(
        display_name="Example model",
        model_id="example-model",
        candidate_type="physically_runnable_local_candidate",
        estimated_memory_gb="4",
        installed_locally="false",
    )
    system_html = render_system_profile_section(
        os_name="macOS",
        machine="arm64",
        memory_text="16 GB",
        memory_status="detected",
        ollama_status="not detected",
        llama_cpp_status="not detected",
    )
    capability_html = render_model_capability_section(
        recommended_tier="small local model",
        physical_notes="Estimate only.",
        workflow_notes="Workflow estimate only.",
        claim_boundary="Recommendations are estimates until validated.",
    )
    runtime_html = render_runtime_status_section(
        runtime_name="Ollama",
        runtime_detected="not detected",
        service_status="not_checked",
        service_url="not configured",
        service_boundary="Service reachability is a localhost-only check. It does not execute models.",
        installed_enabled="disabled",
        installed_method="not_connected",
    )
    catalog_html = render_catalog_installed_section(
        catalog_status="static_local_scaffold",
        local_candidate_name="Example model",
        local_candidate_note="Catalog-only estimate.",
        workflow_candidate_name="Larger workflow example",
        workflow_candidate_note="Larger workflow estimate.",
        installed_status="not_checked",
        installed_count="0",
        catalog_boundary="Catalog examples are not installed models.",
        installed_boundary="No private model directories are scanned.",
    )
    setup_html = render_setup_guidance_section(
        setup_guidance_status="informational_scaffold",
        setup_guidance_url="docs/kora-studio/kora-studio-runtime-setup-guidance.md",
        setup_guidance_boundary="No model is downloaded, no model is executed, no provider call is made.",
    )
    disabled_html = render_disabled_actions_section(
        local_download_label="Download not connected yet",
        local_download_reason="No download action is connected.",
        local_run_label="Run not connected yet",
        local_run_reason="No run action is connected.",
        local_action_boundary="Model actions are disabled planning scaffolds.",
    )
    html = "\n".join([model_option, system_html, capability_html, runtime_html, catalog_html, setup_html, disabled_html])

    assert 'data-kora-model-option="true"' in model_option
    assert 'data-kora-model-option-state="catalog-estimate-only"' in model_option
    assert "Catalog estimate option; not installed or executed by selection." in model_option
    assert "Installed: false" in model_option

    assert "<h2>Your Computer</h2>" in system_html
    assert "No runtime APIs are called by this preview." in system_html
    assert "<h2>Model Capability Estimate</h2>" in capability_html
    assert "Recommendations are estimates until validated." in capability_html
    assert "<h2>Runtime Status</h2>" in runtime_html
    assert "Runtime executable detection is local-only." in runtime_html
    assert "No model execution occurs during this check." in runtime_html
    assert "Installed model detection is not connected yet." in runtime_html
    assert "<h2>Catalog vs Installed</h2>" in catalog_html
    assert "Catalog examples are curated examples, not installed models." in catalog_html
    assert "No private model directories are scanned." in catalog_html
    assert "No runtime model list command is called by default." in catalog_html
    assert "<h2>Setup Guidance</h2>" in setup_html
    assert "No model is downloaded." in setup_html
    assert "No model is executed." in setup_html
    assert "No provider call is made." in setup_html
    assert "<h2>Disabled Download/Run Actions</h2>" in disabled_html
    assert "Download remains disabled until explicitly connected." in disabled_html
    assert "Run remains disabled until explicitly connected." in disabled_html
    assert "No install, download, or model execution action is active in this preview." in disabled_html

    assert "<script" not in html.lower()
    assert "https://" not in html
    assert "fetch(" not in html


def test_harness_request_render_helper_preserves_selector_and_trigger_markers() -> None:
    selector_item = render_local_harness_selector_item(
        request_id="local-harness-json-required-fields-001",
        input_text="Validate required JSON fields.",
        route_class="deterministic_code",
        model_needed="False",
    )
    trigger_item = render_local_harness_trigger_item(
        request_id="local-harness-json-required-fields-001",
        input_text="Validate required JSON fields.",
        task_family="json_validation",
        route_class="deterministic_code",
        model_needed="False",
    )
    selector_html = render_local_harness_request_selector_panels(
        selector_preview_id="local-harness-json-required-fields-001",
        selector_preview_text="Validate required JSON fields.",
        selector_preview_route="deterministic_code",
        selector_preview_model_needed="False",
        selector_items_html=selector_item,
    )
    trigger_html = render_local_harness_trigger_reference_panels(trigger_items_html=trigger_item)
    html = f"{selector_html}\n{trigger_html}"

    assert 'data-kora-component="approved-request-selector"' in html
    assert 'id="kora-selected-request-id">local-harness-json-required-fields-001</code>' in html
    assert 'id="kora-selected-request-text">Validate required JSON fields.</p>' in html
    assert 'id="kora-selected-request-route">deterministic_code</span>' in html
    assert 'id="kora-selected-request-model-needed">False</span>' in html
    assert 'id="kora-run-local-harness-button"' in html
    assert 'aria-describedby="kora-run-local-harness-boundary"' in html
    assert 'id="kora-run-local-harness-boundary"' in html
    assert 'class="request-option"' in html
    assert 'data-kora-keyboard-selectable-request="true"' in html
    assert 'aria-current="false"' in html
    assert 'data-kora-request-id="local-harness-json-required-fields-001"' in html
    assert 'aria-label="Select approved local harness request local-harness-json-required-fields-001"' in html
    assert "Run Local Harness action state" in html
    assert "Approved deterministic sample requests only" in html
    assert "No arbitrary prompt execution" in html
    assert "No model execution" in html
    assert "No provider calls" in html
    assert "No downloads" in html
    assert "This is local preview/demo data, not production evidence" in html
    assert "Model-needed boundary returns <code>execution_not_connected</code>" in html
    assert "<script" not in html.lower()
    assert "https://" not in html
    assert "fetch(" not in html


def test_run_state_render_helper_preserves_retry_and_history_markers() -> None:
    retry_html = render_retry_error_state_panels(selector_preview_id="local-harness-json-required-fields-001")
    history_html = render_local_run_history_panels()
    combined_html = render_run_state_history_panels(selector_preview_id="local-harness-json-required-fields-001")
    html = f"{retry_html}\n{history_html}\n{combined_html}"

    assert 'data-kora-component="retry-error-state"' in html
    assert 'data-kora-diagnostic-hierarchy="secondary"' in html
    assert 'class="card secondary-diagnostic-card"' in html
    assert "Secondary diagnostic error detail." in html
    assert 'id="kora-run-error-state"' in html
    assert "Selected Run Error State" in html
    assert "Retry uses the last approved request only" in html
    assert "No model execution was attempted" in html
    assert "Provider calls remain disabled" in html
    assert "No downloads are connected" in html
    assert "Retry Last Approved Request" in html
    assert "Secondary diagnostic retry control; primary safe next action is also shown in the shell." in html
    assert 'id="kora-last-approved-request-id">local-harness-json-required-fields-001</code>' in html
    assert 'id="kora-retry-available">false</span>' in html
    assert 'id="kora-retry-last-approved-request-button"' in html
    assert "Retry calls only <code>POST /api/harness/run</code> with the last approved" in html
    assert 'data-kora-component="run-history"' in html
    assert "Local Run History" in html
    assert "Secondary diagnostic history." in html
    assert "Browser-local run history" in html
    assert "Page-memory only" in html
    assert "Clears on refresh" in html
    assert 'id="kora-active-history-run-id">none</code>' in html
    assert "History cards show compact counters from generated harness output only" in html
    assert 'id="kora-run-history-count">0</span>' in html
    assert 'id="kora-run-history-status"' in html
    assert "Clear Local Run History" in html
    assert "Secondary diagnostic state reset." in html
    assert 'id="kora-clear-run-history-button"' in html
    assert "Clears browser-local preview state only" in html
    assert "No persistence, no cloud sync, no file export, no file writing, and no backend delete call" in html
    assert 'id="kora-local-run-history"' in html
    assert "<script" not in html.lower()
    assert "https://" not in html
    assert "fetch(" not in html


def test_legacy_render_helper_preserves_collapsed_compatibility_wrapper() -> None:
    html = render_legacy_preview_opening()

    assert '<details class="legacy-preview"' in html
    assert '<details class="legacy-preview" open' not in html
    assert 'data-kora-component="legacy-compatibility-reference"' in html
    assert 'data-kora-legacy-preview-mode="compatibility-collapsed"' in html
    assert 'data-kora-legacy-preview-default="collapsed"' in html
    assert 'data-kora-legacy-preview-role="developer-compatibility-scaffold"' in html
    assert 'data-kora-v1-1-legacy-secondary="developer-reference-only"' in html
    assert 'data-kora-v1-1-legacy-first-run-required="false"' in html
    assert 'data-kora-v1-1-legacy-boundary="secondary-reference-only"' in html
    assert "Legacy detailed preview compatibility scaffold" in html
    assert "Collapsed by default" in html
    assert "The final shell and Details drawer above are the primary local preview" in html
    assert "Developer reference only" in html
    assert "This compatibility scaffold remains local-only and secondary" in html
    assert "does not enable model execution, provider calls, downloads, cloud sync, report export, or report writing" in html
    assert 'class="legacy-preview-content"' in html
    assert "</details>" not in html
    assert "<script" not in html.lower()
    assert "https://" not in html
    assert "fetch(" not in html


def test_style_and_script_render_helpers_preserve_embedded_preview_contract() -> None:
    css = render_studio_css()
    javascript = render_studio_javascript()

    assert STUDIO_CSS_SOURCE_PACKAGE == "kora"
    assert STUDIO_CSS_SOURCE_PATH == "studio_assets/studio.css"
    assert ".studio-shell" in css
    assert ".studio-left-rail" in css
    assert ".model-selector-shell" in css
    assert ".primary-workflow-band" in css
    assert ".primary-workflow-steps" in css
    assert ".primary-workflow-step" in css
    assert ".run-progress-summary" in css
    assert ".run-progress-grid" in css
    assert ".shell-retry-action" in css
    assert ".shell-retry-button" in css
    assert ".secondary-diagnostic-card" in css
    assert ".primary-result-summary" in css
    assert ".primary-result-grid" in css
    assert ".composer-stage" in css
    assert ".details-drawer-shell" in css
    assert "@media (max-width: 760px)" in css
    assert "@media (max-width: 520px)" in css
    assert "button,\nsummary,\n[tabindex=\"0\"]" in css
    assert "min-height: 44px" in css
    assert ".run-progress-grid,\n  .primary-result-grid,\n  .shell-selected-run-grid" in css
    assert "<script" not in css.lower()
    assert "http://" not in css
    assert "https://" not in css

    assert STUDIO_JAVASCRIPT_SOURCE_PACKAGE == "kora"
    assert STUDIO_JAVASCRIPT_SOURCE_PATH == "studio_assets/studio.js"
    assert "window.koraStudioScriptStatus" in javascript
    assert "setLeftRailOpen" in javascript
    assert "setDetailsDrawerOpen" in javascript
    assert "setRunProgressSummary" in javascript
    assert "kora-run-progress-state" in javascript
    assert "kora-shell-retry-guidance" in javascript
    assert "kora-shell-retry-last-approved-request-button" in javascript
    assert "data-kora-retry-last-approved-request-button" in javascript
    assert 'setAttribute("inert", "")' in javascript
    assert 'removeAttribute("inert")' in javascript
    assert 'button.setAttribute("aria-current", isSelected ? "true" : "false")' in javascript
    assert "left_rail_inert" in javascript
    assert "details_drawer_inert" in javascript
    assert "Generated event stream is local harness events only" in javascript
    assert "setPrimaryResultSummary" in javascript
    assert "kora-primary-result-status" in javascript
    assert "renderRunResponse" in javascript
    assert "fetch(\"/api/harness/run\"" in javascript
    assert "fetch(`/api/harness/events?run_id=${encodeURIComponent(selectedRunId)}`)" in javascript
    assert "new EventSource(`/api/harness/sse?run_id=${encodeURIComponent(selectedRunId)}`)" in javascript
    assert "fetch(\"/api/provider" not in javascript
    assert "fetch(\"/api/download" not in javascript
    assert "fetch(\"/api/model" not in javascript
    assert "fetch(\"/api/report" not in javascript
    assert "fetch(\"/api/export" not in javascript
    assert "new EventSource(\"http" not in javascript
    assert "new EventSource(\"/api/provider" not in javascript
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript
    assert "indexedDB" not in javascript


def test_studio_javascript_helper_loads_package_controlled_source_file() -> None:
    javascript_source_path = Path(__file__).resolve().parents[1] / "kora" / "studio_assets" / "studio.js"
    javascript_source = javascript_source_path.read_text(encoding="utf-8")

    assert javascript_source_path.is_file()
    assert javascript_source == render_studio_javascript()
    assert "window.koraStudioScriptStatus" in javascript_source
    assert "fetch(\"/api/harness/run\"" in javascript_source
    assert "new EventSource(`/api/harness/sse?run_id=${encodeURIComponent(selectedRunId)}`)" in javascript_source
    assert "<script" not in javascript_source.lower()
    assert "fetch(\"/api/provider" not in javascript_source
    assert "fetch(\"/api/download" not in javascript_source
    assert "fetch(\"/api/model" not in javascript_source
    assert "fetch(\"/api/report" not in javascript_source
    assert "fetch(\"/api/export" not in javascript_source
    assert "http://" not in javascript_source
    assert "https://" not in javascript_source


def test_studio_css_helper_loads_package_controlled_source_file() -> None:
    css_source_path = Path(__file__).resolve().parents[1] / "kora" / "studio_assets" / "studio.css"
    css_source = css_source_path.read_text(encoding="utf-8")

    assert css_source_path.is_file()
    assert css_source == render_studio_css()
    assert ".studio-shell" in css_source
    assert ".details-drawer-shell" in css_source
    assert "<script" not in css_source.lower()
    assert "http://" not in css_source
    assert "https://" not in css_source


def test_package_data_includes_only_reviewed_protocol_and_studio_assets() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["tool"]["setuptools"]["package-data"]["kora"] == [
        "solution/schemas/*.json",
        "studio_assets/*.css",
        "studio_assets/*.js",
        "benchmarks/assets/*.html",
        "benchmarks/assets/*.css",
        "benchmarks/assets/*.js",
    ]


def test_css_static_asset_path_allowlist_rejects_unsafe_paths() -> None:
    assert get_studio_css_asset_path_status("/studio-assets/studio.css") == ("studio.css", 200)
    assert get_studio_css_asset_path_status("/studio-assets/studio.js") == ("studio.js", 200)
    assert get_studio_asset_path_status("/studio-assets/studio.css") == ("studio.css", 200)
    assert get_studio_asset_path_status("/studio-assets/studio.js") == ("studio.js", 200)
    assert get_studio_css_asset_path_status("/studio-assets") == (None, 404)
    assert get_studio_css_asset_path_status("/studio-assets/") == (None, 404)
    assert get_studio_css_asset_path_status("/studio-assets/unknown.css") == (None, 404)
    assert get_studio_css_asset_path_status("/studio-assets/unknown.js") == (None, 404)
    assert get_studio_css_asset_path_status("/studio-assets/../studio.css") == (None, 400)
    assert get_studio_css_asset_path_status("/studio-assets/%2e%2e/studio.css") == (None, 400)
    assert get_studio_css_asset_path_status("/studio-assets/%252e%252e/studio.css") == (None, 400)
    assert get_studio_css_asset_path_status("/studio-assets/..%2fsecret") == (None, 400)
    assert get_studio_css_asset_path_status("/studio-assets/..\\secret") == (None, 400)
    assert get_studio_css_asset_path_status("/studio-assets//etc/passwd") == (None, 400)


def test_studio_asset_handler_does_not_introduce_filesystem_static_serving() -> None:
    handler_source = inspect.getsource(create_studio_request_handler)
    asset_guard_source = inspect.getsource(get_studio_asset_path_status)

    assert "path.startswith(\"/studio-assets\")" in handler_source
    assert "get_studio_asset_path_status(path)" in handler_source
    assert "render_studio_css()" in handler_source
    assert "render_studio_javascript()" in handler_source
    assert "STUDIO_CSS_ASSET_PATH" in asset_guard_source
    assert "STUDIO_JAVASCRIPT_ASSET_PATH" in asset_guard_source

    forbidden_tokens = [
        "SimpleHTTPRequestHandler",
        "translate_path",
        "list_directory",
        "os.listdir",
        "os.scandir",
        "def send_head",
        "shutil.copyfileobj",
        "open(",
        "Path(",
        "glob(",
    ]
    combined_source = f"{handler_source}\n{asset_guard_source}"
    for token in forbidden_tokens:
        assert token not in combined_source


def test_import_does_not_start_server_or_require_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert os.environ.get("OPENAI_API_KEY") is None
    assert os.environ.get("ANTHROPIC_API_KEY") is None
    assert DEFAULT_STUDIO_HOST == "127.0.0.1"
    assert DEFAULT_STUDIO_PORT == 8765


def test_allowed_studio_hosts_are_local_only() -> None:
    assert is_allowed_studio_host("127.0.0.1") is True
    assert is_allowed_studio_host("localhost") is True
    assert is_allowed_studio_host("0.0.0.0") is False
    assert is_allowed_studio_host("::1") is False


def test_get_studio_server_status_fields() -> None:
    status = get_studio_server_status()

    assert status["ok"] is True
    assert status["service"] == "kora-studio"
    assert status["status"] == "preview"
    assert status["studio_status"]["service"] == "kora-studio"
    assert status["studio_status"]["status"] == "preview"
    assert status["studio_status"]["implementation"] == "local_server_skeleton"
    assert status["studio_status"]["positioning"] == "local-first AI Task Execution Router workspace"
    assert status["studio_status"]["v0_2_status"]["milestone"] == "v0.2"
    assert status["studio_status"]["v0_2_status"]["readiness"] == "local_preview_demo_ready"
    assert "local preview/demo readiness milestone" in status["studio_status"]["v0_2_status"]["claim_boundary"]
    assert status["v0_2_status"] == status["studio_status"]["v0_2_status"]
    assert status["v0_1_readiness_status"] == "local_fixture_demo_ready"
    assert "Report Viewer Placeholder" in status["v0_1_demo_surfaces"]
    assert "local fixture-backed AI Task Execution Router demo scaffold" in status["v0_1_claim_boundary"]
    assert status["server"] == "local-only"
    assert status["host"] == "127.0.0.1"
    assert status["port"] == 8765
    assert status["launch_boundary"] == {
        "host": "127.0.0.1",
        "port": 8765,
        "url": "http://127.0.0.1:8765/",
        "server": "local-only",
        "allowed_hosts": ["127.0.0.1", "localhost"],
        "provider_calls_enabled": False,
        "cloud_sync_enabled": False,
        "browser_launch_available": True,
        "api_key_required": False,
        "claim_boundary": (
            "The Studio preview is localhost-only by default. Provider calls and cloud sync are disabled, "
            "and no API key is required for the default local preview."
        ),
    }
    assert status["provider_calls_enabled"] is False
    assert status["cloud_sync_enabled"] is False
    assert status["system_profile"]["default_host"] == "127.0.0.1"
    assert status["system_profile"]["default_port"] == 8765
    assert status["system_profile"]["provider_calls_enabled"] is False
    assert status["system_profile"]["cloud_sync_enabled"] is False
    assert status["model_capability_estimate"]["recommended_local_chat_tier"]
    assert "estimates until validated" in status["model_capability_estimate"]["claim_boundary"]
    assert status["model_catalog_status"] == "static_local_scaffold"
    assert status["recommended_models"]
    first_model = status["recommended_models"][0]
    assert first_model["download_action_enabled"] is False
    assert first_model["run_action_enabled"] is False
    assert first_model["download_action_label"] == "Download not connected yet"
    assert first_model["run_action_label"] == "Run not connected yet"
    assert first_model["disabled_actions_route_to_guidance"] is True
    assert first_model["setup_guidance_path"] == "docs/kora-studio/kora-studio-runtime-setup-guidance.md"
    assert "estimates until validated" in status["model_catalog_claim_boundary"]
    assert "Download and execution are not connected yet" in status["model_catalog_claim_boundary"]
    assert status["runtime_status"]
    first_runtime = status["runtime_status"][0]
    assert first_runtime["service_reachable"] is False
    assert first_runtime["service_check_status"] == "not_checked"
    assert first_runtime["service_url"] == "http://127.0.0.1:11434/"
    assert first_runtime["service_probe_timeout_ms"] <= 500
    assert "localhost-only check" in first_runtime["service_probe_claim_boundary"]
    assert first_runtime["installed_model_detection_enabled"] is False
    assert first_runtime["installed_model_detection_status"] == "not_connected"
    assert first_runtime["installed_models_count"] == 0
    assert status["installed_models_summary"]["detection_status"] == "not_connected"
    assert status["installed_models_summary"]["installed_model_detection_status"] == "not_connected"
    assert status["installed_models_summary"]["installed_model_detection_enabled"] is False
    assert status["installed_models_summary"]["installed_models_count"] == 0
    assert "Catalog examples are not the same as installed models" in status["catalog_runtime_distinction"]
    assert status["setup_guidance_status"] == "informational_scaffold"
    assert status["setup_guidance_url"] == "docs/kora-studio/kora-studio-runtime-setup-guidance.md"
    assert status["disabled_actions_route_to_guidance"] is True
    assert status["disabled_action_state"] == {
        "download_connected": False,
        "run_connected": False,
        "model_execution_connected": False,
        "provider_calls_enabled": False,
        "cloud_sync_enabled": False,
        "disabled_actions_route_to_guidance": True,
        "setup_guidance_url": "docs/kora-studio/kora-studio-runtime-setup-guidance.md",
        "claim_boundary": (
            "Download and run actions remain disabled until explicitly connected. Disabled actions point to "
            "informational setup guidance, not to an active installer or model runner."
        ),
    }
    assert "not to an active installer" in status["setup_guidance_claim_boundary"]
    assert status["local_harness_status"]["status"] == "local_deterministic_harness_available"
    assert status["local_harness_status"]["event_source_status"] == "generated_events_available"
    assert status["local_harness_status"]["run_trigger_status"] == "api_endpoint_connected"
    assert status["local_harness_status"]["run_trigger_endpoint"] == "/api/harness/run"
    assert status["local_harness_status"]["run_retrieval_endpoint"] == "/api/harness/run/{run_id}"
    assert status["local_harness_status"]["events_endpoint"] == "/api/harness/events?run_id=<id>"
    assert status["local_harness_status"]["events_endpoint_status"] == "generated_events_retrieval_connected"
    assert status["local_harness_status"]["sse_endpoint"] == "/api/harness/sse?run_id=<id>"
    assert status["local_harness_status"]["sse_endpoint_status"] == "generated_events_stream_connected"
    assert status["local_harness_status"]["approved_request_ids_only"] is True
    assert status["local_harness_status"]["arbitrary_prompt_execution_connected"] is False
    assert status["local_harness_status"]["sample_request_count"] == 5
    assert status["local_harness_status"]["provider_calls_enabled"] is False
    assert status["local_harness_status"]["cloud_sync_enabled"] is False
    assert status["local_harness_status"]["model_execution_connected"] is False
    assert status["local_harness_status"]["download_connected"] is False
    assert status["local_harness_run_store"]["run_store_status"] == "in_memory_local_only"
    assert status["local_harness_run_store"]["persistence_enabled"] is False
    assert status["local_harness_run_store"]["provider_calls_enabled"] is False
    assert status["local_harness_run_store"]["model_execution_connected"] is False
    assert "approved synthetic deterministic request IDs" in status["local_harness_run_claim_boundary"]
    assert status["local_harness_request_summary"]["local_harness_request_count"] == 5
    assert status["local_harness_requests"][0]["request_id"] == "local-harness-json-required-fields-001"
    assert status["local_harness_sample_run"]["request_id"] == "local-harness-json-required-fields-001"
    assert status["local_harness_sample_run"]["events"][0]["stage_id"] == "request_received"
    assert status["local_harness_sample_run"]["events"][-1]["stage_id"] == "final_counters"
    assert status["local_harness_counters"]["baseline_model_calls"] == 1
    assert status["local_harness_counters"]["kora_model_calls"] == 0
    assert status["local_harness_counters"]["avoided_model_calls"] == 1
    assert "synthetic deterministic requests" in status["local_harness_claim_boundary"]
    assert status["local_harness_comparison_status"] == "local_deterministic_harness_generated"
    assert status["local_harness_comparison"]["comparison_source"] == "local_harness_summary"
    assert status["comparison_counters"]["baseline_model_calls"] == 1
    assert status["comparison_counters"]["kora_model_calls"] == 0
    assert status["comparison_counters"]["avoided_model_calls"] == 1
    assert "local deterministic harness data" in status["comparison_claim_boundary"]
    assert status["execution_viewer_status"] == "fixture_mock_scaffold"
    assert status["execution_viewer_fixture_event_count"] == 6
    assert status["execution_viewer_fixture_events"][0]["stage_id"] == "request_received"
    assert status["execution_viewer_fixture_events"][-1]["stage_id"] == "final_counters"
    assert status["execution_viewer_fixture_events"][-1]["counters_snapshot"]["avoided_model_calls"] == 1
    assert "local fixture/mock data" in status["execution_viewer_claim_boundary"]
    assert status["model_execution_connected"] is False
    assert status["download_connected"] is False
    assert status["standard_vs_kora_comparison_status"] == "fixture_mock_scaffold"
    assert status["standard_vs_kora_metrics"]["baseline_model_calls"] == 1
    assert status["standard_vs_kora_metrics"]["kora_model_calls"] == 0
    assert status["standard_vs_kora_metrics"]["avoided_model_calls"] == 1
    assert status["standard_vs_kora_metrics"]["deterministic_routes"] == 1
    assert status["standard_vs_kora_metrics"]["model_escalations"] == 0
    assert status["standard_vs_kora_metrics"]["validation_pass_count"] == 1
    assert len(status["standard_vs_kora_metric_cards"]) == 6
    assert "fixture/mock comparison" in status["standard_vs_kora_claim_boundary"]
    assert status["report_viewer_status"] == "local_harness_summary_placeholder"
    assert status["report_viewer_placeholder"]["report_source"] == "local_harness_summary"
    assert status["report_viewer_placeholder"]["report_fixture_path"] == (
        "docs/kora-studio/fixtures/report-viewer-metadata.sample.json"
    )
    assert status["report_viewer_placeholder"]["arbitrary_local_file_scan_enabled"] is False
    assert status["report_viewer_placeholder"]["upload_enabled"] is False
    assert status["report_viewer_placeholder"]["generated_report_commit_enabled"] is False
    assert status["report_viewer_placeholder"]["file_export_enabled"] is False
    assert status["report_viewer_placeholder"]["file_written"] is False
    assert status["report_viewer_placeholder"]["model_execution_connected"] is False
    assert status["report_viewer_placeholder"]["production_evidence_claim"] is False
    assert status["report_viewer_placeholder"]["cost_claim_enabled"] is False
    assert status["report_viewer_placeholder"]["energy_claim_enabled"] is False
    assert status["report_viewer_placeholder"]["counters"] == status["local_harness_counters"]
    assert status["report_viewer_placeholder"]["counters"]["avoided_model_calls"] == 1
    assert status["report_export_status"] == "placeholder_not_connected"
    assert status["report_export_placeholder"]["export_action_enabled"] is False
    assert "local summary metadata only" in status["report_viewer_claim_boundary"]
    assert set(status["claim_boundaries"]) == {
        "studio",
        "launch",
        "model_capability",
        "model_catalog",
        "runtime_setup_guidance",
        "disabled_actions",
        "execution_viewer",
        "standard_vs_kora",
        "report_viewer",
        "local_harness",
        "local_harness_run",
        "local_harness_comparison",
    }
    assert "not a production release" in status["claim_boundaries"]["studio"]
    assert "localhost-only" in status["claim_boundaries"]["launch"]
    assert "estimates until validated" in status["claim_boundaries"]["model_capability"]
    assert "Download and execution are not connected yet" in status["claim_boundaries"]["model_catalog"]
    assert "No model is downloaded" in status["claim_boundaries"]["runtime_setup_guidance"]
    assert "remain disabled" in status["claim_boundaries"]["disabled_actions"]
    assert "local fixture/mock data" in status["claim_boundaries"]["execution_viewer"]
    assert "fixture/mock comparison" in status["claim_boundaries"]["standard_vs_kora"]
    assert "local summary metadata only" in status["claim_boundaries"]["report_viewer"]
    assert "synthetic deterministic requests" in status["claim_boundaries"]["local_harness"]
    assert "approved synthetic deterministic request IDs" in status["claim_boundaries"]["local_harness_run"]
    assert "local deterministic harness data" in status["claim_boundaries"]["local_harness_comparison"]
    assert status["first_run_section_order"] == [
        "Launch/local-only status",
        "Your Computer",
        "Model Capability Estimate",
        "Runtime Status",
        "Catalog vs Installed",
        "Setup Guidance",
        "Disabled Download/Run Actions",
        "KORA Boost Boundary",
        "Local Harness Preview",
        "Execution Viewer",
        "Standard Mode vs KORA Boost",
        "Report Viewer Placeholder",
    ]
    assert status["browser_launch_available"] is True
    assert status["ollama_calls_enabled"] is False
    assert status["local_runtime_required"] is False
    assert status["no_server_side_provider_calls"] is True
    assert status["docs_path"] == "docs/kora-studio/README.md"
    assert status["fixtures_path"] == "docs/kora-studio/fixtures/"
    assert status["kora_boost_message"] == APPROVED_BOOST_MESSAGE
    assert status["kora_boost_technical_explanation"] == TECHNICAL_EXPLANATION


def test_health_and_status_payloads_are_claim_safe() -> None:
    health = get_studio_health_payload()
    status = get_studio_status_payload()

    assert health == {
        "ok": True,
        "service": "kora-studio",
        "status": "preview",
        "server": "local-only",
        "provider_calls_enabled": False,
        "cloud_sync_enabled": False,
        "browser_launch_available": True,
    }
    assert status["provider_calls_enabled"] is False
    assert status["cloud_sync_enabled"] is False
    assert "system_profile" in status
    assert "model_capability_estimate" in status
    assert "recommended_models" in status
    assert status["model_catalog_status"] == "static_local_scaffold"
    assert "runtime_status" in status
    assert "installed_models_summary" in status
    assert status["installed_models_summary"]["installed_model_detection_enabled"] is False
    assert status["setup_guidance_status"] == "informational_scaffold"
    assert status["disabled_actions_route_to_guidance"] is True
    assert status["execution_viewer_status"] == "fixture_mock_scaffold"
    assert status["execution_viewer_fixture_event_count"] == 6
    assert status["local_harness_status"]["status"] == "local_deterministic_harness_available"
    assert status["local_harness_status"]["run_trigger_status"] == "api_endpoint_connected"
    assert status["local_harness_requests"]
    assert status["local_harness_sample_run"]["status"] == "completed"
    assert status["local_harness_counters"]["avoided_model_calls"] == 1
    assert status["local_harness_status"]["model_execution_connected"] is False
    assert status["local_harness_comparison_status"] == "local_deterministic_harness_generated"
    assert status["comparison_counters"]["avoided_model_calls"] == 1
    assert status["local_harness_comparison"]["model_execution_connected"] is False
    assert status["model_execution_connected"] is False
    assert status["standard_vs_kora_comparison_status"] == "fixture_mock_scaffold"
    assert status["standard_vs_kora_metrics"]["avoided_model_calls"] == 1
    assert status["report_viewer_status"] == "local_harness_summary_placeholder"
    assert status["report_viewer_placeholder"]["report_source"] == "local_harness_summary"
    assert status["report_export_status"] == "placeholder_not_connected"
    assert status["no_server_side_provider_calls"] is True
    assert status["kora_boost_message"] == APPROVED_BOOST_MESSAGE


def test_status_payload_exposes_v0_2_contract_fields() -> None:
    status = get_studio_status_payload()

    required_top_level_fields = {
        "studio_status",
        "launch_boundary",
        "system_profile",
        "model_capability_estimate",
        "runtime_status",
        "installed_models_summary",
        "model_catalog_status",
        "recommended_models",
        "setup_guidance_status",
        "disabled_action_state",
        "execution_viewer_status",
        "execution_viewer_fixture_events",
        "local_harness_status",
        "local_harness_run_store",
        "local_harness_requests",
        "local_harness_sample_run",
        "local_harness_counters",
        "local_harness_claim_boundary",
        "local_harness_run_claim_boundary",
        "local_harness_comparison_status",
        "local_harness_comparison",
        "comparison_counters",
        "comparison_claim_boundary",
        "standard_vs_kora_comparison_status",
        "standard_vs_kora_comparison",
        "standard_vs_kora_metrics",
        "report_viewer_status",
        "report_viewer_placeholder",
        "provider_calls_enabled",
        "cloud_sync_enabled",
        "claim_boundaries",
        "first_run_section_order",
    }
    assert required_top_level_fields <= set(status)

    assert status["studio_status"]["v0_2_status"]["first_run_section_order"] == status["first_run_section_order"]
    assert status["launch_boundary"]["provider_calls_enabled"] is False
    assert status["launch_boundary"]["cloud_sync_enabled"] is False
    assert status["disabled_action_state"]["download_connected"] is False
    assert status["disabled_action_state"]["run_connected"] is False
    assert status["disabled_action_state"]["model_execution_connected"] is False
    assert status["execution_viewer_status"] == "fixture_mock_scaffold"
    assert status["standard_vs_kora_comparison_status"] == "fixture_mock_scaffold"
    assert status["report_viewer_status"] == "local_harness_summary_placeholder"
    assert status["provider_calls_enabled"] is False
    assert status["cloud_sync_enabled"] is False


def test_render_studio_server_status_text_includes_boundaries() -> None:
    text = render_studio_server_status_text(get_studio_server_status())

    assert "Launching KORA Studio" in text
    assert "Local URL:" in text
    assert "http://127.0.0.1:8765/" in text
    assert "Local-only" in text
    assert "Provider calls: disabled" in text
    assert "Cloud sync: disabled" in text
    assert "Press Ctrl+C to stop" in text


def test_render_studio_server_status_text_includes_no_browser_state() -> None:
    text = render_studio_server_status_text(get_studio_server_status(), open_browser=False)

    assert "Local URL:" in text
    assert "http://127.0.0.1:8765/" in text
    assert "Browser launch: disabled by --no-browser." in text


def test_render_studio_server_status_text_includes_browser_failure_fallback() -> None:
    text = render_studio_server_status_text(
        get_studio_server_status(),
        open_browser=True,
        browser_opened=False,
    )

    assert "Browser launch failed. Open this URL manually:" in text
    assert "http://127.0.0.1:8765/" in text


def test_open_studio_browser_is_mockable_and_failure_safe() -> None:
    opened_urls: list[str] = []

    assert open_studio_browser("http://127.0.0.1:8765/", lambda url: (opened_urls.append(url), False)[1]) is False
    assert opened_urls == ["http://127.0.0.1:8765/"]

    def raise_error(url: str) -> bool:
        raise RuntimeError(f"cannot open {url}")

    assert open_studio_browser("http://127.0.0.1:8765/", raise_error) is False
    assert open_studio_browser("http://127.0.0.1:8765/", lambda url: True) is True


def test_run_studio_server_opens_browser_by_default(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    opened_urls: list[str] = []
    created_servers: list[object] = []

    class FakeServer:
        def __init__(self, address: tuple[str, int], handler: object) -> None:
            self.address = address
            self.handler = handler
            created_servers.append(self)

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            return None

    monkeypatch.setattr("kora.studio_server.ThreadingHTTPServer", FakeServer)

    run_studio_server(browser_opener=lambda url: opened_urls.append(url) is None or True)

    assert opened_urls == [get_studio_url()]
    assert created_servers
    assert getattr(created_servers[0], "address") == ("127.0.0.1", 8765)
    output = capsys.readouterr().out
    assert "Launching KORA Studio" in output
    assert "Provider calls: disabled" in output
    assert "Cloud sync: disabled" in output


def test_run_studio_server_no_browser_suppresses_browser_open(monkeypatch: pytest.MonkeyPatch) -> None:
    opened_urls: list[str] = []

    class FakeServer:
        def __init__(self, address: tuple[str, int], handler: object) -> None:
            self.address = address
            self.handler = handler

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            return None

    monkeypatch.setattr("kora.studio_server.ThreadingHTTPServer", FakeServer)

    run_studio_server(open_browser=False, browser_opener=lambda url: opened_urls.append(url) is None or True)

    assert opened_urls == []


def test_request_handler_serves_health_status_and_placeholder() -> None:
    handler = create_studio_request_handler(lambda: get_studio_server_status(port=0))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    except PermissionError:
        pytest.skip("localhost binding is not available in this sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
            health_csp = response.headers.get("Content-Security-Policy")
            health = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(f"{base_url}/status", timeout=2) as response:
            status_csp = response.headers.get("Content-Security-Policy")
            status = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(f"{base_url}/studio-assets/studio.css", timeout=2) as response:
            css_content_type = response.headers.get("Content-Type", "")
            css_cache_control = response.headers.get("Cache-Control", "")
            css_csp = response.headers.get("Content-Security-Policy")
            css = response.read().decode("utf-8")
        with urllib.request.urlopen(f"{base_url}/studio-assets/studio.js", timeout=2) as response:
            javascript_content_type = response.headers.get("Content-Type", "")
            javascript_cache_control = response.headers.get("Cache-Control", "")
            javascript_csp = response.headers.get("Content-Security-Policy")
            javascript = response.read().decode("utf-8")
        with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
            html = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            html_csp = response.headers.get("Content-Security-Policy", "")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert health["ok"] is True
    assert health_csp is None
    assert health["service"] == "kora-studio"
    assert status["server"] == "local-only"
    assert status_csp is None
    assert status["provider_calls_enabled"] is False
    assert status["cloud_sync_enabled"] is False
    assert "system_profile" in status
    assert "model_capability_estimate" in status
    assert "recommended_models" in status
    assert status["model_catalog_claim_boundary"]
    assert "runtime_status" in status
    assert status["installed_models_summary"]["installed_models_detected"] is False
    assert status["ollama_calls_enabled"] is False
    assert "text/css" in css_content_type
    assert "charset=utf-8" in css_content_type
    assert css_cache_control == "no-store"
    assert css_csp is None
    assert ".studio-shell" in css
    assert ".details-drawer-shell" in css
    assert "<script" not in css.lower()
    assert "http://" not in css
    assert "https://" not in css
    assert "application/javascript" in javascript_content_type
    assert "charset=utf-8" in javascript_content_type
    assert javascript_cache_control == "no-store"
    assert javascript_csp is None
    assert "window.koraStudioScriptStatus" in javascript
    assert "fetch(\"/api/harness/run\"" in javascript
    assert "new EventSource(`/api/harness/sse?run_id=${encodeURIComponent(selectedRunId)}`)" in javascript
    assert "<script" not in javascript.lower()
    assert "http://" not in javascript
    assert "https://" not in javascript

    assert "text/html" in content_type
    assert html_csp == STUDIO_LOCAL_PREVIEW_CSP
    assert "default-src 'none'" in html_csp
    assert "style-src 'self'" in html_csp
    assert "script-src 'self'" in html_csp
    assert "connect-src 'self'" in html_csp
    assert "frame-ancestors 'none'" in html_csp
    assert "object-src 'none'" in html_csp
    assert "form-action 'none'" in html_csp
    assert "http:" not in html_csp
    assert "https:" not in html_csp
    assert "*" not in html_csp
    assert "unsafe-inline" not in html_csp
    assert "unsafe-eval" not in html_csp
    assert "KORA Studio" in html
    assert '<link rel="stylesheet" href="/studio-assets/studio.css">' in html
    assert '<script src="/studio-assets/studio.js"></script>' in html
    assert "<style>" not in html.lower()
    assert APPROVED_BOOST_MESSAGE in html
    assert "Preview / Local-only" in html
    assert "Local Preview Scaffold" in html
    assert "deterministic-first local workflow exploration" in html
    assert "/health" in html
    assert "/status" in html
    assert "/api/harness/run" in html
    assert "/api/harness/events" in html
    assert "/api/harness/sse" in html
    assert "not model token streaming" in html
    assert "Provider calls: disabled" in html
    assert "Cloud sync: disabled" in html
    assert "Your Computer" in html
    assert "Model Capability Estimate" in html
    assert "Catalog vs Installed" in html
    assert "Physically runnable local candidates" in html
    assert "Larger-model workflow candidates" in html
    assert "Model recommendations are estimates until validated on this machine" in html
    assert "Download and execution are not connected yet" in html
    assert "Download" in html
    assert "Run" in html
    assert "Disabled Download/Run Actions" in html
    assert "Download action" in html
    assert "Run action" in html
    assert "Download not connected yet" in html
    assert "Run not connected yet" in html
    assert "Setup Guidance" in html
    assert "Disabled actions point to guidance, not to an active installer" in html
    assert "No model is downloaded" in html
    assert "No model is executed" in html
    assert "Provider/cloud routes are disabled by default" in html
    assert "docs/kora-studio/kora-studio-runtime-setup-guidance.md" in html
    assert "Runtime Status" in html
    assert "Installed locally" in html
    assert "Service reachability is a localhost-only check" in html
    assert "No model execution occurs during this check" in html
    assert "Installed model detection is not connected yet" in html
    assert "No private model directories are scanned" in html
    assert "No runtime model list command is called by default" in html
    assert "Download and run actions remain disabled" in html
    assert "Catalog vs Installed" in html
    assert "Catalog examples are not installed models" in html
    assert "Estimated local model tier" in html
    assert "KORA Boost Boundary" in html
    assert "KORA does not remove RAM/VRAM/unified-memory requirements" in html
    assert "Local Harness Preview" in html
    assert "local_deterministic_harness_available" in html
    assert "generated_events_available" in html
    assert "api_endpoint_connected" in html
    assert "Run Local Harness" in html
    assert "Run Local Harness action state" in html
    assert "Approved deterministic sample requests only" in html
    assert "No arbitrary prompt execution" in html
    assert "Generated harness events only" in html
    assert "This is local preview/demo data, not production evidence" in html
    assert "execution_not_connected" in html
    assert "Available local deterministic sample requests" in html
    assert "local-harness-json-required-fields-001" in html
    assert "Expected route: deterministic_code" in html
    assert "Harness event stages" in html
    assert "Generated Event Timeline" in html
    assert "Generated local harness events only" in html
    assert "Not model token streaming" in html
    assert "No provider output" in html
    assert "Route class: input" in html
    assert "Status: completed" in html
    assert "Model called: False" in html
    assert "Deterministic route used:" in html
    assert "Validation result:" in html
    assert "Latency:" in html
    assert "Model-needed boundaries do not execute models in this milestone" in html
    assert "Local deterministic harness output" in html
    assert "Generated Counters" in html
    assert "Model/runtime integration: not connected" in html
    assert "Browser launch: available" in html
    assert "Ollama integration: not connected" in html
    assert "No production/API-cost/energy claims" in html
    assert "Report Viewer Placeholder" in html
    assert "Local Harness Summary Report" in html
    assert "docs/kora-studio/fixtures/report-viewer-metadata.sample.json" in html
    assert "No arbitrary local file scan is performed" in html
    assert "No cloud upload is connected" in html
    assert "Export not connected yet" in html
    assert "Local harness summary only" in html
    assert "No new benchmark evidence is created" in html
    assert "provider calls enabled" not in html.lower()
    assert "production cost reduction" not in html.lower()
    assert "real api-cost reduction" not in html.lower()
    assert "energy reduction" not in html.lower()


def test_request_handler_triggers_and_retrieves_local_harness_run() -> None:
    clear_local_harness_run_records()
    handler = create_studio_request_handler(lambda: get_studio_server_status(port=0))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    except PermissionError:
        pytest.skip("localhost binding is not available in this sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        request_body = json.dumps({"request_id": "local-harness-known-faq-001"}).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/api/harness/run",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            run = json.loads(response.read().decode("utf-8"))

        with urllib.request.urlopen(f"{base_url}/api/harness/run/{run['run_id']}", timeout=2) as response:
            retrieved_run = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(f"{base_url}/api/harness/events?run_id={run['run_id']}", timeout=2) as response:
            events_payload = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(f"{base_url}/api/harness/sse?run_id={run['run_id']}", timeout=2) as response:
            sse_content_type = response.headers.get("Content-Type", "")
            sse_stream = response.read().decode("utf-8")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert run["ok"] is True
    assert run["request_id"] == "local-harness-known-faq-001"
    assert run["run_status"] == "completed"
    assert run["created_at"].endswith("Z")
    assert run["completed_at"].endswith("Z")
    assert run["generated_events"][0]["stage_id"] == "request_received"
    assert run["generated_events"][-1]["stage_id"] == "final_counters"
    assert run["generated_counters"]["structured_lookup_routes"] == 1
    assert run["generated_counters"]["kora_model_calls"] == 0
    assert run["comparison_summary"]["metrics"]["avoided_model_calls"] == 1
    assert run["report_metadata_summary"]["report_source"] == "local_harness_summary"
    assert run["report_metadata_summary"]["report_source_detail"] == "local deterministic harness output / fixture metadata"
    assert run["report_metadata_summary"]["run_id"] == run["run_id"]
    assert run["report_metadata_summary"]["request_id"] == run["request_id"]
    assert run["report_metadata_summary"]["event_count"] == len(run["generated_events"])
    assert run["report_metadata_summary"]["counter_summary"]["structured_lookup_routes"] == 1
    assert run["report_metadata_summary"]["comparison_summary_status"] == "local_deterministic_harness_generated"
    assert run["report_metadata_summary"]["model_execution_status"] == "not_needed"
    assert run["report_metadata_summary"]["provider_calls_enabled"] is False
    assert run["report_metadata_summary"]["cloud_sync_enabled"] is False
    assert run["report_metadata_summary"]["file_export_enabled"] is False
    assert run["report_metadata_summary"]["file_written"] is False
    assert run["report_metadata_summary"]["export_action_enabled"] is False
    assert run["report_metadata_summary"]["production_evidence_claim"] is False
    assert "local summary metadata only" in run["report_metadata_summary"]["claim_boundary"]
    assert run["provider_calls_enabled"] is False
    assert run["cloud_sync_enabled"] is False
    assert run["model_execution_connected"] is False
    assert run["download_connected"] is False
    assert retrieved_run == run
    assert events_payload["run_id"] == run["run_id"]
    assert events_payload["request_id"] == run["request_id"]
    assert events_payload["run_status"] == "completed"
    assert events_payload["event_count"] == len(events_payload["events"])
    assert events_payload["events"] == run["generated_events"]
    assert events_payload["sse_connected"] is False
    assert events_payload["streaming_connected"] is False
    assert events_payload["model_execution_connected"] is False
    assert "text/event-stream" in sse_content_type
    assert "event: stream_started" in sse_stream
    assert "event: harness_stage" in sse_stream
    assert "event: stream_completed" in sse_stream
    assert run["run_id"] in sse_stream
    assert "request_received" in sse_stream
    assert "final_counters" in sse_stream
    assert "approved synthetic deterministic request IDs" in sse_stream
    assert "model_token_streaming_connected" in sse_stream
    assert sse_stream.index("event: stream_started") < sse_stream.index("event: harness_stage")
    assert sse_stream.index("stage_id\":\"request_received") < sse_stream.index("stage_id\":\"final_counters")


def test_request_handler_rejects_invalid_local_harness_run_request() -> None:
    clear_local_harness_run_records()
    handler = create_studio_request_handler(lambda: get_studio_server_status(port=0))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    except PermissionError:
        pytest.skip("localhost binding is not available in this sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        request_body = json.dumps({"request_id": "missing-request"}).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/api/harness/run",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request, timeout=2)
        error_body = json.loads(exc_info.value.read().decode("utf-8"))

        with pytest.raises(urllib.error.HTTPError) as missing_run_exc:
            urllib.request.urlopen(f"{base_url}/api/harness/run/missing-run", timeout=2)
        missing_run_body = json.loads(missing_run_exc.value.read().decode("utf-8"))
        with pytest.raises(urllib.error.HTTPError) as missing_events_exc:
            urllib.request.urlopen(f"{base_url}/api/harness/events?run_id=missing-run", timeout=2)
        missing_events_body = json.loads(missing_events_exc.value.read().decode("utf-8"))
        with pytest.raises(urllib.error.HTTPError) as missing_sse_exc:
            urllib.request.urlopen(f"{base_url}/api/harness/sse?run_id=missing-run", timeout=2)
        missing_sse_body = json.loads(missing_sse_exc.value.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert exc_info.value.code == 404
    assert error_body["ok"] is False
    assert error_body["error"] == "unknown_request_id"
    assert error_body["request_id"] == "missing-request"
    assert error_body["run_status"] == "failed"
    assert error_body["provider_calls_enabled"] is False
    assert error_body["model_execution_connected"] is False

    assert missing_run_exc.value.code == 404
    assert missing_run_body["error"] == "run_not_found"
    assert missing_events_exc.value.code == 404
    assert missing_events_body["error"] == "run_not_found"
    assert missing_events_body["model_execution_connected"] is False
    assert missing_sse_exc.value.code == 404
    assert missing_sse_body["error"] == "run_not_found"
    assert missing_sse_body["model_execution_connected"] is False


def test_static_preview_html_content_is_safe_and_complete() -> None:
    html = render_studio_placeholder_html(get_studio_server_status())
    css = render_studio_css()
    javascript = render_studio_javascript()

    assert html.startswith("<!doctype html>")
    assert "KORA Studio" in html
    required_component_markers = [
        "shell-layout",
        "left-rail",
        "boundary-strip",
        "top-model-selector",
        "primary-workflow-band",
        "run-progress-summary",
        "shell-retry-action",
        "primary-result-summary",
        "composer",
        "approved-request-selector",
        "selected-run-summary",
        "selected-run-event-timeline",
        "selected-run-counters",
        "selected-run-comparison",
        "selected-run-report-metadata",
        "right-details-drawer",
        "run-history",
        "retry-error-state",
        "generated-event-stream-status",
        "legacy-compatibility-reference",
    ]
    for component in required_component_markers:
        assert f'data-kora-component="{component}"' in html
    assert "data-kora-final-ui-shell=\"true\"" in html
    assert 'data-kora-v1-preview-readiness="shell-first-boundary-consolidation"' in html
    assert 'data-kora-v1-shell-local-only-status="visible"' in html
    assert 'data-kora-v1-1-shell-only-hardening="active"' in html
    assert 'data-kora-v1-1-shell-only-coverage="boundaries,drawer-diagnostics,selected-run,legacy-secondary"' in html
    assert 'data-kora-responsive-shell="mobile-overlay-ready"' in html
    assert 'data-kora-mobile-visual-qa="v0.9"' in html
    assert 'data-kora-mobile-breakpoint="max-width-760"' in html
    assert 'data-kora-mobile-qa-surfaces="left-rail,model-selector,composer,right-drawer,boundary-pills"' in html
    assert 'data-kora-mobile-no-overlap-contract="true"' in html
    assert 'data-kora-keyboard-focus-pass="true"' in html
    assert 'data-kora-focus-visible-controls="shell-and-harness"' in html
    assert "KORA Studio left mini rail" in html
    assert 'data-kora-mobile-rail="collapsed-overlay"' in html
    assert 'data-kora-rail-open="false"' in html
    assert 'id="kora-left-rail"' in html
    assert 'data-kora-rail-state="closed"' in html
    assert 'id="kora-left-rail-toggle"' in html
    assert 'aria-controls="kora-left-rail"' in html
    assert 'data-kora-rail-toggle="true"' in html
    assert 'id="kora-left-rail-close"' in html
    assert 'data-kora-rail-close="true"' in html
    assert "setLeftRailOpen" in javascript
    assert "isSmallRailViewport" in javascript
    assert 'data-kora-rail-state") === "open"' in javascript
    assert "Open left rail" in html
    assert "Close left rail" in html
    assert "New task" in html
    assert "Search tasks" in html
    assert "Local workspace" in html
    assert "Cloud sync disabled" in html
    assert "Search or select open-source LLM" in html
    assert 'data-kora-model-selector="local-catalog-scaffold"' in html
    assert 'data-kora-mobile-selector="compact-overlay-menu"' in html
    assert 'data-kora-model-selection-state="catalog-estimate-only"' in html
    assert 'aria-describedby="kora-model-selector-boundary"' in html
    assert 'id="kora-model-selector-boundary"' in html
    assert 'data-kora-model-selector-menu="true"' in html
    assert 'data-kora-model-selected-estimate="true"' in html
    assert 'data-kora-model-selected-label="catalog-estimate-only"' in html
    assert 'data-kora-model-selection-status="selected-estimate"' in html
    assert 'aria-selected="true"' in html
    assert 'data-kora-model-option-state="catalog-estimate-only"' in html
    assert "Catalog-only estimate selected" in html
    assert "Selected local fit estimate; catalog-only state" in html
    assert "Catalog estimate option; not installed or executed by selection" in html
    assert 'data-kora-model-option="true"' in html
    assert "Selected estimate: Example mini local model" in html
    assert "Catalog suggestions are local static examples, not installed models" in html
    assert "Selecting a model here does not install, download, or execute it" in html
    assert "Selection does not install, download, or execute this model" in html
    assert "Recommended local catalog options shown:" in html
    assert "KORA Studio top bar" in html
    assert "KORA Studio centered composer" in html
    assert 'data-kora-responsive-accessibility-check="v3.8"' in html
    assert 'data-kora-primary-path-a11y="labels-focus-keyboard-status"' in html
    assert "What do you want to work on?" in html
    assert "Choose a local model once. KORA keeps routing details out of the way." in html
    assert 'data-kora-component="primary-workflow-band"' in html
    assert 'data-kora-primary-operator-path="select-run-review-inspect"' in html
    assert 'data-kora-responsive-stack="single-column-under-760"' in html
    assert 'class="primary-workflow-steps" role="list"' in html
    assert 'role="list"' in html
    assert 'role="listitem"' in html
    assert 'aria-hidden="true">1</span>' in html
    assert "Primary local demo workflow" in html
    assert "Select approved request" in html
    assert "Run Local Harness" in html
    assert "Review result summary" in html
    assert "Inspect timeline/details" in html
    assert "Use approved local harness requests only." in html
    assert "Run the selected request ID locally." in html
    assert "Read generated local harness output only." in html
    assert "Open generated events and drawer diagnostics if needed." in html
    assert (
        "Local preview only. No arbitrary prompt execution, model execution, provider calls, downloads, "
        "cloud sync, report export, or file writing."
    ) in html
    assert "Ask KORA..." in html
    assert 'id="kora-composer-run-local-harness-button"' in html
    assert 'aria-describedby="kora-composer-action-note"' in html
    assert 'id="kora-composer-action-note"' in html
    assert "Composer action uses the selected approved local harness request only" in html
    assert "Composer selected-run summary" in html
    assert 'id="kora-composer-selected-run-summary"' in html
    assert 'id="kora-composer-request-id"' in html
    assert 'id="kora-composer-run-status"' in html
    assert 'id="kora-composer-run-id"' in html
    assert 'data-kora-component="run-progress-summary"' in html
    assert 'data-kora-run-progress-surface="idle-running-events-completed-failed"' in html
    assert 'data-kora-primary-status-a11y="polite-atomic"' in html
    assert 'aria-atomic="true"' in html
    assert "Run progress" in html
    assert "Follow the selected local harness run state before opening generated event diagnostics." in html
    assert 'id="kora-run-progress-state"' in html
    assert 'id="kora-run-progress-step"' in html
    assert 'id="kora-run-progress-event-status"' in html
    assert 'id="kora-run-progress-stream-status"' in html
    assert 'id="kora-run-progress-error"' in html
    assert "No run selected" in html
    assert "No generated events yet" in html
    assert "Generated event stream idle" in html
    assert "not model token streaming or provider output" in html
    assert 'data-kora-component="shell-retry-action"' in html
    assert 'data-kora-retry-boundary="last-approved-request-only"' in html
    assert "Safe next action" in html
    assert 'id="kora-shell-retry-guidance"' in html
    assert "No retry needed. Select an approved request, run Local Harness, or inspect diagnostics if a run fails." in html
    assert 'id="kora-shell-retry-last-approved-request-button"' in html
    assert 'data-kora-retry-last-approved-request-button="true"' in html
    assert 'aria-describedby="kora-shell-retry-guidance kora-shell-retry-boundary-note"' in html
    assert 'id="kora-shell-retry-boundary-note"' in html
    assert "Retry reuses only the last approved request ID." in html
    assert "No arbitrary prompt execution, model execution, provider calls, downloads, report export, or file writing." in html
    assert 'data-kora-component="primary-result-summary"' in html
    assert 'data-kora-result-summary-before-diagnostics="true"' in html
    assert 'data-kora-primary-result-a11y="polite-atomic"' in html
    assert "Result summary" in html
    assert "Review the selected request, final run status, key generated counters, comparison status, and report metadata before opening lower-level diagnostics." in html
    assert 'id="kora-primary-result-request-id"' in html
    assert 'id="kora-primary-result-run-id"' in html
    assert 'id="kora-primary-result-status"' in html
    assert 'id="kora-primary-result-event-count"' in html
    assert 'id="kora-primary-result-avoided-model-calls"' in html
    assert 'id="kora-primary-result-deterministic-routes"' in html
    assert 'id="kora-primary-result-comparison-status"' in html
    assert 'id="kora-primary-result-report-status"' in html
    assert 'id="kora-primary-result-boundary"' in html
    assert "Generated local harness output only. Not production telemetry, not production cost evidence" in html
    assert 'data-kora-shell-selected-run-surface="v1.0"' in html
    assert 'data-kora-shell-selected-run-coverage="timeline,counters,comparison,report-metadata"' in html
    assert 'data-kora-v1-1-selected-run-polish="shell-drawer-status"' in html
    assert 'aria-label="Secondary diagnostics status"' in html
    assert 'data-kora-diagnostic-hierarchy="secondary"' in html
    assert "secondary-diagnostic-card" in html
    assert "Secondary diagnostic timeline." in html
    assert "Secondary diagnostic counters." in html
    assert "Secondary diagnostic comparison." in html
    assert "Secondary diagnostic report metadata." in html
    assert "Diagnostics status" in html
    assert 'id="kora-shell-selected-timeline-status"' in html
    assert 'id="kora-shell-selected-counters-status"' in html
    assert 'id="kora-shell-selected-comparison-status"' in html
    assert 'id="kora-shell-selected-report-status"' in html
    assert "Shell selected-run surface mirrors generated local harness output only" in html
    assert "Details drawer mirrors the same selected-run status so legacy preview is not required for normal inspection" in html
    assert html.index('data-kora-component="run-progress-summary"') < html.index('data-kora-component="primary-result-summary"')
    assert html.index('data-kora-component="run-progress-summary"') < html.index('data-kora-shell-selected-run-surface="v1.0"')
    assert html.index('data-kora-component="primary-result-summary"') < html.index('data-kora-shell-selected-run-surface="v1.0"')
    assert html.index('data-kora-component="primary-result-summary"') < html.index('data-kora-component="selected-run-event-timeline"')
    assert "Provider calls disabled" in html
    assert "Cloud sync disabled" in html
    assert "Downloads disabled" in html
    assert "Model execution not connected yet" in html
    assert "Report export disabled" in html
    assert 'data-kora-shell-local-only-boundary="v1.0"' in html
    assert 'data-kora-shell-boundary-coverage="provider,cloud,download,model-execution,report-export"' in html
    assert "Shell-first boundary: approved local harness requests only" in html
    assert "no report file export or writing" in html
    assert 'id="kora-details-drawer-toggle"' in html
    assert 'aria-controls="kora-details-drawer"' in html
    assert 'aria-expanded="false"' in html
    assert 'data-kora-drawer-toggle="true"' in html
    assert 'id="kora-details-drawer"' in html
    assert 'data-kora-drawer-state="closed"' in html
    assert 'data-kora-keyboard-trap-boundary="closed-inert-open-focus-managed"' in html
    assert 'aria-hidden="true"' in html
    assert 'tabindex="-1" inert' in html
    assert 'id="kora-details-drawer-close"' in html
    assert 'data-kora-drawer-close="true"' in html
    assert 'data-kora-drawer-open="true"' in css
    assert "setDetailsDrawerOpen" in javascript
    assert 'event.key === "Escape"' in javascript
    assert "KORA Studio right details drawer scaffold" in html
    assert 'data-kora-mobile-drawer="right-overlay"' in html
    assert "Inspector · local preview" in html
    assert 'data-kora-drawer-section="runtime-status"' in html
    assert 'data-kora-drawer-section="selected-model"' in html
    assert 'data-kora-drawer-section="catalog-vs-installed"' in html
    assert 'data-kora-drawer-section="route-trace"' in html
    assert 'data-kora-drawer-section="generated-counters"' in html
    assert 'data-kora-drawer-section="selected-run-surfaces"' in html
    assert 'data-kora-drawer-selected-run-coverage="timeline,counters,comparison,report-metadata"' in html
    assert 'data-kora-v1-1-drawer-selected-run-polish="primary-diagnostics"' in html
    assert 'id="kora-drawer-selected-run-id"' in html
    assert 'id="kora-drawer-selected-timeline-status"' in html
    assert 'id="kora-drawer-selected-counters-status"' in html
    assert 'id="kora-drawer-selected-comparison-status"' in html
    assert 'id="kora-drawer-selected-report-status"' in html
    assert "Drawer selected-run diagnostics mirror shell state for normal inspection" in html
    assert 'data-kora-drawer-section="report-metadata"' in html
    assert 'data-kora-drawer-section="claim-boundaries"' in html
    assert (
        'data-kora-drawer-boundary-coverage="provider,cloud,download,model-execution,report-export,private-scan,runtime-list"'
        in html
    )
    assert "Selection does not install or run a model" in html
    assert "Route trace" in html
    assert "Generated harness events only." in html
    assert "Not production telemetry" in html
    assert "Not production cost evidence" in html
    assert "Report metadata preview only" in html
    assert "Report metadata" in html
    assert "File export:" in html
    assert "File written:" in html
    assert "Claim boundaries" in html
    assert "No private model directory scanning" in html
    assert "No runtime model list commands" in html

    assert '<details class="legacy-preview"' in html
    assert '<main class="legacy-preview"' not in html
    assert '<details class="legacy-preview" open' not in html
    assert "legacy-preview" in html
    assert 'data-kora-legacy-preview-mode="compatibility-collapsed"' in html
    assert 'data-kora-legacy-preview-default="collapsed"' in html
    assert 'data-kora-legacy-preview-role="developer-compatibility-scaffold"' in html
    assert 'data-kora-v1-1-legacy-secondary="developer-reference-only"' in html
    assert 'data-kora-v1-1-legacy-first-run-required="false"' in html
    assert 'data-kora-v1-1-legacy-boundary="secondary-reference-only"' in html
    assert "Legacy detailed preview compatibility scaffold" in html
    assert "Collapsed by default" in html
    assert "The final shell and Details drawer above are the primary local preview" in html
    assert "not required for first-run understanding" in html
    assert "Developer reference only" in html
    assert "This compatibility scaffold remains local-only and secondary" in html
    assert "Local Preview Scaffold" in html
    assert "Preview / Local-only" in html
    assert APPROVED_BOOST_MESSAGE in html
    assert TECHNICAL_EXPLANATION in html
    assert "deterministic-first local workflow exploration" in html
    assert "Launch / Local-only Status" in html
    assert "First-run order" in html
    assert "Server: local" in html
    assert "Provider calls: disabled" in html
    assert "Cloud sync: disabled" in html
    assert "Your Computer" in html
    assert "Model Capability Estimate" in html
    assert "Catalog vs Installed" in html
    assert "Catalog examples" in html
    assert "static_local_scaffold" in html
    assert "Download and execution are not connected yet" in html
    assert "Disabled Download/Run Actions" in html
    assert "Download action" in html
    assert "Run action" in html
    assert "Download not connected yet" in html
    assert "Run not connected yet" in html
    assert "Setup Guidance" in html
    assert "Disabled actions point to guidance, not to an active installer" in html
    assert "No model is downloaded" in html
    assert "No model is executed" in html
    assert "Runtime Status" in html
    assert "Installed model detection" in html
    assert "Runtime executable detection is local-only" in html
    assert "Service reachability is a localhost-only check" in html
    assert "No model execution occurs during this check" in html
    assert "Installed model detection is not connected yet" in html
    assert "No private model directories are scanned" in html
    assert "No runtime model list command is called by default" in html
    assert "Download and run actions remain disabled" in html
    assert "Catalog examples are not installed models" in html
    assert "Estimated local model tier" in html
    assert "Unknown until validated" in html or "depending on runtime" in html
    assert "KORA does not remove RAM/VRAM/unified-memory requirements" in html
    assert "Local Harness Preview" in html
    assert "local_deterministic_harness_available" in html
    assert "generated_events_available" in html
    assert "Run trigger: api_endpoint_connected" in html
    assert "Approved Request Selector" in html
    assert "Interactive approved request selector" in html
    assert "Approved local harness requests only" in html
    assert "Approved request only" in html
    assert "Selected request preview" in html
    assert "Selector state is browser-local in-memory page state only" in html
    assert 'data-kora-keyboard-selectable-request="true"' in html
    assert 'aria-label="Select approved local harness request local-harness-json-required-fields-001"' in html
    assert 'aria-pressed="false"' in html
    assert 'aria-current="false"' in html
    assert "id=\"kora-run-local-harness-button\"" in html
    assert "kora-composer-run-local-harness-button" in html
    assert "id=\"kora-selected-run-state\"" in html
    assert "Selected run state" in html
    assert "Selected Run Error State" in html
    assert "id=\"kora-run-error-state\"" in html
    assert "Retry Last Approved Request" in html
    assert "id=\"kora-retry-last-approved-request-button\"" in html
    assert "id=\"kora-last-approved-request-id\"" in html
    assert "Retry uses the last approved request only" in html
    assert "The local harness endpoint was unavailable" in javascript
    assert "The local response could not be parsed" in javascript
    assert "lastApprovedRequestId" in javascript
    assert "retryAvailable" in javascript
    assert "runError" in javascript
    assert "runLoading" in javascript
    assert "await runLocalHarness(lastApprovedRequestId)" in javascript
    assert "Local Run History" in html
    assert "Browser-local run history" in html
    assert "Page-memory only" in html
    assert "Clears on refresh" in html
    assert "Active selected run: <code id=\"kora-active-history-run-id\">none</code>" in html
    assert "History cards show compact counters from generated harness output only" in html
    assert "id=\"kora-local-run-history\"" in html
    assert "id=\"kora-run-history-count\"" in html
    assert "id=\"kora-run-history-status\"" in html
    assert "Clear Local Run History" in html
    assert "id=\"kora-clear-run-history-button\"" in html
    assert "Cleared browser-local preview state only" in javascript
    assert (
        "Resets selected-run UI, selected events, selected counters, selected comparison, selected report metadata, and page-memory history"
        in html
    )
    assert "No persistence, no cloud sync, no file export, no file writing, and no backend delete call" in html
    assert "let runHistory = []" in javascript
    assert "const runHistoryLimit = 5" in javascript
    assert "renderRunHistory" in javascript
    assert "selectRunFromHistory" in javascript
    assert "addRunToHistory" in javascript
    assert "clearLocalRunHistory" in javascript
    assert "getShellAccessibilityState" in javascript
    assert "setShellSelectedRunSurfaceState" in javascript
    assert "kora-drawer-selected-run-id" in html
    assert "window.koraStudioAccessibilityState" in javascript
    assert "window.koraStudioScriptStatus" in javascript
    assert 'status: "ready"' in javascript
    assert "keyboard_focus_pass" in javascript
    assert "left_rail_expanded" in javascript
    assert "left_rail_inert" in javascript
    assert "details_drawer_expanded" in javascript
    assert "details_drawer_inert" in javascript
    assert "data-kora-history-run-id" in javascript
    assert "Active selected local run" in javascript
    assert "Recent local run" in javascript
    assert "Compact counters: avoided_model_calls=" in javascript
    assert "aria-current" in javascript
    assert "Selected in page" in javascript
    assert "No backend records, files, report exports, or server endpoints were deleted" in javascript
    assert "get run_history()" in javascript
    assert "get selected_run_record()" in javascript
    assert "Generated Event Stream" in html
    assert "id=\"kora-sse-status\"" in html
    assert "id=\"kora-sse-fallback-used\"" in html
    assert "id=\"kora-sse-error\"" in html
    assert "Generated harness events only" in html
    assert "Not model token streaming" in html
    assert "No provider streaming" in html
    assert "Fallback to local events endpoint available" in html
    assert "let sseAvailable = typeof EventSource !== \"undefined\"" in javascript
    assert "let activeEventSource = null" in javascript
    assert "closeActiveEventSource" in javascript
    assert "connectGeneratedEventStream" in javascript
    assert "new EventSource(`/api/harness/sse?run_id=${encodeURIComponent(selectedRunId)}`)" in javascript
    assert "fetchSelectedEventsFallback" in javascript
    assert "eventSource.addEventListener(\"harness_stage\"" in javascript
    assert "eventSource.addEventListener(\"stream_completed\"" in javascript
    assert "get sse_status()" in javascript
    assert "get sse_fallback_used()" in javascript
    assert "Generated local harness output only" in html
    assert "Selected Run Event Timeline" in html
    assert "id=\"kora-selected-run-events\"" in html
    assert "id=\"kora-selected-events-status\"" in html
    assert "No selected run events loaded yet" in html
    assert "Events are fetched from <code>GET /api/harness/events?run_id=&lt;id&gt;</code>" in html
    assert "Selected Run Counters" in html
    assert "id=\"kora-selected-run-counters\"" in html
    assert "id=\"kora-selected-counters-status\"" in html
    assert "Run an approved local harness request to view selected-run counters" in html
    assert "Selected Run: Standard Mode vs KORA Boost" in html
    assert "id=\"kora-selected-run-comparison\"" in html
    assert "id=\"kora-selected-comparison-status\"" in html
    assert "Run an approved local harness request to view selected-run comparison" in html
    assert "Selected Run Report Metadata" in html
    assert "id=\"kora-selected-run-report-metadata\"" in html
    assert "id=\"kora-selected-report-status\"" in html
    assert "Run an approved local harness request to view selected-run report metadata" in html
    assert "Report metadata preview only" in html
    assert "No file export" in html
    assert "No file writing" in html
    assert "Generated local harness counters only" in html
    assert "Not production telemetry" in html
    assert "Not production cost evidence" in html
    assert "selectedRunId" in javascript
    assert "selectedRunEvents" in javascript
    assert "selectedRunCounters" in javascript
    assert "selectedRunComparison" in javascript
    assert "selectedRunReportMetadata" in javascript
    assert "data-kora-request-id" in html
    assert "Local deterministic harness data only" in html
    assert "Run Local Harness" in html
    assert "Run Local Harness action state" in html
    assert "The browser button calls only the local harness run endpoint for an approved request id" in html
    assert "Approved deterministic sample requests only" in html
    assert "No arbitrary prompt execution" in html
    assert "Generated harness events only" in html
    assert "This is local preview/demo data, not production evidence" in html
    assert "Model-needed boundary returns <code>execution_not_connected</code>" in html
    assert "Available sample requests: 5" in html
    assert "Available local deterministic sample requests" in html
    assert "local-harness-json-required-fields-001" in html
    assert "Harness event stages" in html
    assert "Generated Event Timeline" in html
    assert "Generated local harness events only" in html
    assert "Not model token streaming" in html
    assert "No provider output" in html
    assert "Route class: input" in html
    assert "Status: completed" in html
    assert "Model called: False" in html
    assert "Deterministic route used:" in html
    assert "Validation result:" in html
    assert "Latency:" in html
    assert "Model-needed boundaries do not execute models in this milestone" in html
    assert "Local deterministic harness output" in html
    assert "Generated Counters" in html
    assert "Standard Mode vs KORA Boost" in html
    assert "Local deterministic harness comparison" in html
    assert "Local Harness Comparison boundary" in html
    assert "Comparison is generated from local deterministic harness output" in html
    assert "This is not production cost evidence" in html
    assert "This does not execute a model" in html
    assert "local_deterministic_harness_generated" in html
    assert "Baseline model calls" in html
    assert "KORA model calls" in html
    assert "Avoided model calls" in html
    assert "Deterministic routes" in html
    assert "Model escalations" in html
    assert "Validation passes" in html
    assert "No cost or energy claim is made" in html
    assert "Model/runtime integration: not connected" in html
    assert "Browser launch: available" in html
    assert "Ollama integration: not connected" in html
    assert "Endpoint Panel" in html
    assert "/health" in html
    assert "/status" in html
    assert "/api/harness/run" in html
    assert "/api/harness/events" in html
    assert "/api/harness/sse" in html
    assert "It streams no model tokens" in html
    assert "Execution Viewer" in html
    assert "Fixture/mock events only" in html
    assert "No real model execution" in html
    assert "No provider calls" in html
    assert "No model downloads" in html
    assert "Request received" in html
    assert "Deterministic route check" in html
    assert "Structured lookup" in html
    assert "Validation pass" in html
    assert "Model fallback skipped" in html
    assert "Final counters" in html
    assert "No runtime execution occurs on this page" in html
    assert "Report Viewer Placeholder" in html
    assert "Local Harness Report" in html
    assert "Report Metadata Preview" in html
    assert "Report metadata preview only" in html
    assert "Report Boundary" in html
    assert "Local deterministic harness output only" in html
    assert "Not production evidence" in html
    assert "No file export in this preview" in html
    assert "File export: disabled" in html
    assert "File written: false" in html
    assert "Report metadata" in html
    assert "Export placeholder" in html
    assert "Boundary warnings" in html
    assert "No arbitrary local file scan is performed" in html
    assert "No cloud upload is connected" in html
    assert "Export not connected yet" in html
    assert "No new benchmark evidence is created" in html
    assert "Limitations Panel" in html
    assert "No production/API-cost/energy claims" in html
    assert "No full frontend yet" in html
    assert "Browser launch is local-only" in html
    assert "No provider calls" in html
    assert "No model/runtime integration yet" in html
    assert "No Ollama integration" in html
    assert "docs/kora-studio/README.md" in html
    assert "docs/kora-studio/fixtures/" in html
    assert "Local-only skeleton" in html
    assert "OPENAI_API_KEY" not in html
    assert "ANTHROPIC_API_KEY" not in html
    assert "provider calls enabled" not in html.lower()
    assert "download now" not in html.lower()
    assert "run now" not in html.lower()
    assert "install now" not in html.lower()
    assert "production cost reduction" not in html.lower()
    assert "real api-cost reduction" not in html.lower()
    assert "energy reduction" not in html.lower()
    assert "production report" not in html.lower()
    assert "cost reduction proven" not in html.lower()
    assert "real provider report" not in html.lower()
    assert "model output report" not in html.lower()
    assert "download report" not in html.lower()
    assert "export now" not in html.lower()
    assert "<script" in html.lower()
    assert '<script src="/studio-assets/studio.js"></script>' in html
    assert "type=\"application/json\" id=\"kora-approved-requests-data\"" in html
    assert "fetch(\"/api/harness/run\"" in javascript
    assert "fetch(`/api/harness/events?run_id=${encodeURIComponent(selectedRunId)}`)" in javascript
    assert javascript.index("renderRunResponse(payload);") < javascript.index("await connectGeneratedEventStream();")
    assert "renderSelectedCounters(run.generated_counters" in javascript
    assert "renderSelectedComparison(run.comparison_summary" in javascript
    assert "renderSelectedReportMetadata(run.report_metadata_summary)" in javascript
    assert "JSON.stringify({request_id: requestId})" in javascript
    assert "Retry any prompt" not in html
    assert "Type a prompt" not in html
    assert 'src="/studio-assets/studio.js"' in html
    assert 'href="http' not in html.lower()
    assert "https://" not in html.lower()
    assert "localstorage" not in html.lower()
    assert "sessionstorage" not in html.lower()
    assert "indexeddb" not in html.lower()
    assert "fetch(\"/api/delete" not in javascript
    assert "fetch(\"/api/harness/delete" not in javascript
    assert "fetch(\"/api/harness/sse" not in javascript
    assert "new EventSource(\"http" not in javascript
    assert "new EventSource(\"/api/model" not in javascript
    assert "new EventSource(\"/api/provider" not in javascript
    assert "new EventSource(\"/api/download" not in javascript
    assert "fetch(\"/api/model" not in html
    assert "fetch(\"/api/provider" not in html
    assert "fetch(\"/api/download" not in html
    assert "fetch(\"/api/report" not in html
    assert "fetch(\"/api/export" not in html
    assert "fetch(\"/api/file" not in html
    assert "xmlhttprequest" not in html.lower()
    assert "navigator.sendbeacon" not in html.lower()
    assert "<input" not in html.lower()
    assert "<textarea" not in html.lower()
    assert "Run any prompt" not in html
    assert "Run model" not in html
    assert "Download model" not in html
    assert "Production benchmark" not in html

    ordered_sections = [
        "Launch / Local-only Status",
        "Your Computer",
        "Model Capability Estimate",
        "Runtime Status",
        "Catalog vs Installed",
        "Setup Guidance",
        "Disabled Download/Run Actions",
        "KORA Boost Boundary",
        "Local Harness Preview",
        "Execution Viewer",
        "Standard Mode vs KORA Boost",
        "Report Viewer Placeholder",
    ]
    positions = [html.index(f"<h2>{section}</h2>") for section in ordered_sections]
    assert positions == sorted(positions)


def test_studio_root_html_resource_types_remain_csp_compatible() -> None:
    html = render_studio_placeholder_html(get_studio_server_status())
    assert _find_studio_html_resource_policy_violations(html) == []

    parser = _parse_studio_html_resources(html)

    assert parser.inline_style_attributes == []

    assert _stylesheet_hrefs(parser) == EXPECTED_STUDIO_STYLESHEETS

    src_scripts, inline_scripts = _script_groups(parser)
    assert src_scripts == [EXPECTED_STUDIO_SCRIPT]
    assert inline_scripts == [EXPECTED_APPROVED_REQUEST_JSON_SCRIPT]

    for tag, attr_name, url in parser.resource_urls:
        assert not url.startswith(("data:", "blob:", "http://", "https://", "//")), (tag, attr_name, url)

    resource_urls = {url for _, _, url in parser.resource_urls}
    assert "/studio-assets/studio.css" in resource_urls
    assert "/studio-assets/studio.js" in resource_urls
    assert all(
        not url.startswith("/studio-assets/") or url in ALLOWED_STUDIO_ASSET_URLS
        for url in resource_urls
    )


def test_static_preview_html_exposes_keyboard_selector_contract() -> None:
    html = render_studio_placeholder_html(get_studio_server_status())

    assert 'data-kora-keyboard-selector-contract="v4.2"' in html
    required_keyboard_contracts = [
        "mobile-left-rail",
        "mobile-rail-toggle",
        "mobile-rail-close",
        "model-selector",
        "details-drawer-toggle",
        "details-drawer",
        "details-drawer-close",
        "primary-run-local-harness",
        "approved-request-selector",
        "approved-request-option",
        "lower-run-local-harness",
        "run-progress-summary",
        "shell-retry-last-approved-request",
        "primary-result-summary",
        "secondary-diagnostics-status",
        "secondary-generated-event-stream",
        "secondary-event-timeline",
        "secondary-run-counters",
        "secondary-run-comparison",
        "secondary-report-metadata",
        "secondary-retry-last-approved-request",
    ]
    for contract in required_keyboard_contracts:
        assert f'data-kora-keyboard-contract="{contract}"' in html

    assert 'id="kora-left-rail-toggle"' in html
    assert 'aria-controls="kora-left-rail"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="kora-left-rail"' in html
    assert 'data-kora-rail-state="closed"' in html
    assert 'id="kora-left-rail-close"' in html

    assert 'id="kora-details-drawer-toggle"' in html
    assert 'aria-controls="kora-details-drawer"' in html
    assert 'id="kora-details-drawer"' in html
    assert 'data-kora-drawer-state="closed"' in html
    assert 'data-kora-keyboard-trap-boundary="closed-inert-open-focus-managed"' in html
    assert 'aria-hidden="true"' in html
    assert 'tabindex="-1" inert' in html
    assert 'id="kora-details-drawer-close"' in html

    assert 'data-kora-keyboard-selectable-request="true"' in html
    assert 'aria-pressed="false"' in html
    assert 'aria-current="false"' in html
    assert 'id="kora-composer-run-local-harness-button"' in html
    assert 'id="kora-run-local-harness-button"' in html
    assert 'id="kora-shell-retry-last-approved-request-button"' in html
    assert 'disabled>Retry Last Approved Request</button>' in html

    assert 'data-kora-component="run-progress-summary"' in html
    assert 'data-kora-primary-status-a11y="polite-atomic"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-atomic="true"' in html
    assert 'data-kora-component="primary-result-summary"' in html
    assert 'data-kora-primary-result-a11y="polite-atomic"' in html


def test_studio_root_csp_remains_narrow_for_current_resource_types() -> None:
    assert _find_csp_source_policy_violations(STUDIO_LOCAL_PREVIEW_CSP) == []

    directives = _parse_csp_directives(STUDIO_LOCAL_PREVIEW_CSP)

    assert directives == EXPECTED_STUDIO_CSP_DIRECTIVES

    for directive, sources in directives.items():
        assert not set(CSP_FORBIDDEN_SOURCES).intersection(sources), directive
        assert all("://" not in source for source in sources), directive
    for directive in CSP_NEW_RESOURCE_DIRECTIVES_REQUIRING_REVIEW:
        assert directive not in directives


def test_studio_package_assets_do_not_introduce_remote_or_embedded_resource_urls() -> None:
    css = render_studio_css()
    javascript = render_studio_javascript()

    assert _find_css_resource_policy_violations(css) == []

    for source in (css, javascript):
        lowered = source.lower()
        for token in PACKAGE_ASSET_FORBIDDEN_TOKENS:
            assert token not in lowered

    for token, _violation in CSS_FORBIDDEN_PATTERNS:
        assert token not in css.lower()


@pytest.mark.parametrize(
    ("name", "html", "expected_violation"),
    [
        (
            "inline style attribute",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><main style="display:block"></main><script src="/studio-assets/studio.js"></script></body></html>',
            "inline style attribute",
        ),
        (
            "inline executable script",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><script>alert("blocked")</script><script src="/studio-assets/studio.js"></script></body></html>',
            "inline script must be approved request JSON",
        ),
        (
            "external script URL",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><script src="https://cdn.example/studio.js"></script></body></html>',
            "executable script must be /studio-assets/studio.js",
        ),
        (
            "external stylesheet URL",
            '<html><head><link rel="stylesheet" href="https://cdn.example/studio.css"></head>'
            '<body><script src="/studio-assets/studio.js"></script></body></html>',
            "stylesheet must be /studio-assets/studio.css",
        ),
        (
            "data image resource",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">'
            '<script src="/studio-assets/studio.js"></script></body></html>',
            "data URL resource",
        ),
        (
            "blob resource",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><img src="blob:http://127.0.0.1/example">'
            '<script src="/studio-assets/studio.js"></script></body></html>',
            "blob URL resource",
        ),
        (
            "protocol-relative URL",
            '<html><head><link rel="stylesheet" href="//cdn.example/studio.css"></head>'
            '<body><script src="/studio-assets/studio.js"></script></body></html>',
            "remote resource URL",
        ),
        (
            "unapproved studio asset",
            '<html><head><link rel="stylesheet" href="/studio-assets/theme.css"></head>'
            '<body><script src="/studio-assets/studio.js"></script></body></html>',
            "unapproved studio asset",
        ),
        (
            "mixed-case external resource scheme",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><img src="HTTPS://cdn.example/image.png"><script src="/studio-assets/studio.js"></script></body></html>',
            "remote resource URL",
        ),
        (
            "whitespace-padded resource URL",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><img src="  https://cdn.example/image.png  ">'
            '<script src="/studio-assets/studio.js"></script></body></html>',
            "remote resource URL",
        ),
        (
            "javascript pseudo URL",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><a href="javascript:alert(1)">blocked</a><script src="/studio-assets/studio.js"></script></body></html>',
            "javascript pseudo URL",
        ),
        (
            "srcset external URL",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><img srcset="/studio-assets/studio.css 1x, https://cdn.example/image.png 2x">'
            '<script src="/studio-assets/studio.js"></script></body></html>',
            "remote resource URL",
        ),
        (
            "meta refresh URL",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css">'
            '<meta http-equiv="refresh" content="0;url=https://cdn.example/redirect"></head>'
            '<body><script src="/studio-assets/studio.js"></script></body></html>',
            "remote resource URL",
        ),
        (
            "form action target",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><form action="https://cdn.example/post"></form><script src="/studio-assets/studio.js"></script></body></html>',
            "remote resource URL",
        ),
        (
            "inline event handler",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"></head>'
            '<body><button onclick="alert(1)">blocked</button><script src="/studio-assets/studio.js"></script></body></html>',
            "inline event handler",
        ),
        (
            "inline style block",
            '<html><head><link rel="stylesheet" href="/studio-assets/studio.css"><style>body{display:block}</style></head>'
            '<body><script src="/studio-assets/studio.js"></script></body></html>',
            "inline style block",
        ),
    ],
)
def test_studio_html_resource_violation_fixture_matrix(name: str, html: str, expected_violation: str) -> None:
    violations = _find_studio_html_resource_policy_violations(html)

    assert expected_violation in violations, name


@pytest.mark.parametrize(
    ("name", "csp", "expected_violation"),
    [
        ("wildcard CSP source", "default-src 'none'; script-src *", "wildcard CSP source"),
        ("unsafe-inline", "default-src 'none'; script-src 'self' 'unsafe-inline'", "unsafe-inline"),
        ("unsafe-eval", "default-src 'none'; script-src 'self' 'unsafe-eval'", "unsafe-eval"),
        ("data CSP source", "default-src 'none'; img-src data:", "data CSP source"),
        ("blob CSP source", "default-src 'none'; worker-src blob:", "blob CSP source"),
        ("external CSP host", "default-src 'none'; script-src https://cdn.example", "external CSP host"),
        ("new image directive", f"{STUDIO_LOCAL_PREVIEW_CSP}; img-src 'self'", "new resource directive img-src"),
        ("new font directive", f"{STUDIO_LOCAL_PREVIEW_CSP}; font-src 'self'", "new resource directive font-src"),
    ],
)
def test_studio_csp_violation_fixture_matrix(name: str, csp: str, expected_violation: str) -> None:
    violations = _find_csp_source_policy_violations(csp)

    assert expected_violation in violations, name


@pytest.mark.parametrize(
    ("name", "css", "expected_violation"),
    [
        ("CSS @import", "@import url('https://fonts.example/css'); .studio-shell {}", "CSS @import"),
        ("CSS url", ".studio-shell { background-image: url('/studio-assets/bg.png'); }", "CSS url"),
        ("data CSS URL", ".studio-shell { background: url('data:image/svg+xml,<svg></svg>'); }", "data URL resource"),
        ("blob CSS URL", ".studio-shell { background: url('blob:http://127.0.0.1/example'); }", "blob URL resource"),
        ("external CSS URL", ".studio-shell { background: url('https://cdn.example/bg.png'); }", "remote resource URL"),
    ],
)
def test_studio_css_violation_fixture_matrix(name: str, css: str, expected_violation: str) -> None:
    violations = _find_css_resource_policy_violations(css)

    assert expected_violation in violations, name


def test_request_handler_rejects_unsafe_static_asset_paths() -> None:
    handler = create_studio_request_handler(lambda: get_studio_server_status(port=0))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    except PermissionError:
        pytest.skip("localhost binding is not available in this sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(urllib.error.HTTPError) as unknown_exc:
            urllib.request.urlopen(f"{base_url}/studio-assets/unknown.css", timeout=2)
        unknown_body = unknown_exc.value.read().decode("utf-8")

        with pytest.raises(urllib.error.HTTPError) as directory_exc:
            urllib.request.urlopen(f"{base_url}/studio-assets/", timeout=2)
        directory_body = directory_exc.value.read().decode("utf-8")

        unsafe_paths = [
            "/studio-assets/../studio.css",
            "/studio-assets/%2e%2e/studio.css",
            "/studio-assets/..%5csecret",
            "/studio-assets//etc/passwd",
        ]
        unsafe_errors: list[tuple[int, str]] = []
        for path in unsafe_paths:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"{base_url}{path}", timeout=2)
            unsafe_errors.append((exc_info.value.code, exc_info.value.read().decode("utf-8")))
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert unknown_exc.value.code == 404
    assert directory_exc.value.code == 404
    assert "asset_not_found" in unknown_body
    assert "asset_not_found" in directory_body
    assert "passwd" not in unknown_body
    assert "passwd" not in directory_body
    for code, body in unsafe_errors:
        assert code in {400, 404}
        assert "asset_not_found" in body
        assert "/Users/" not in body
        assert "02_PROJECTS" not in body
        assert "passwd" not in body

def test_runtime_setup_guidance_doc_is_claim_safe() -> None:
    doc = Path("docs/kora-studio/kora-studio-runtime-setup-guidance.md").read_text()

    assert "Setup guidance is informational in this scaffold" in doc
    assert "Disabled actions point to guidance, not to an active installer" in doc
    assert "No model is downloaded" in doc
    assert "No model is executed" in doc
    assert "No private model directories are scanned" in doc
    assert "No runtime model list command is called" in doc
    assert "No provider call is made" in doc
    assert "Provider and cloud routes are disabled by default" in doc
