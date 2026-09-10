"""Embedded into the self-contained notebook by build_deliverables.py."""
try:
    import ipywidgets as widgets
    from IPython.display import HTML, display, clear_output
    WIDGETS_AVAILABLE = True
except ImportError:
    WIDGETS_AVAILABLE = False


def get_api_key():
    """Read credentials only when running live. Never display them or save them in reports."""
    if SECRET_SCOPE and SECRET_KEY:
        if "dbutils" not in globals():
            raise ValueError("Databricks secrets require a Databricks session.")
        return dbutils.secrets.get(scope=SECRET_SCOPE, key=SECRET_KEY)
    return os.getenv("AZURE_OPENAI_API_KEY", "")


def upload_bytes(value):
    """Support both ipywidgets 7 and 8 FileUpload representations."""
    if not value:
        raise ValueError("Choose a regulation file first.")
    if isinstance(value, dict):
        name, item = next(iter(value.items()))
        return item.get("metadata", {}).get("name", name), bytes(item["content"])
    item = value[0]
    return item["name"], bytes(item["content"])


def resolve_regulation(source, version, upload_value=None, path=""):
    if source == "Fictional demo standard":
        return parse_document("demo_regulation.md", DEMO_REGULATION.encode(), "DEMO 2026-09 · FICTIONAL")
    if source == "No regulation":
        return None
    if source == "Upload regulation":
        name, content = upload_bytes(upload_value)
    else:
        if not path.strip():
            raise ValueError("Enter the uploaded file's /Workspace/... or /Volumes/... path.")
        file_path = Path(path.strip())
        if file_path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Regulation must be at most 10 MB.")
        name, content = file_path.name, file_path.read_bytes()
    return parse_document(name, content, version)


def run_review(claims_text, disclosure_text, regulation, mode="Offline demo"):
    context = prepare(claims_text, disclosure_text, regulation)
    if mode == "Offline demo":
        findings, warnings = demo_analysis(context)
    else:
        key = get_api_key()
        if not key and "localhost" not in API_URL and "127.0.0.1" not in API_URL:
            raise ValueError("Configure a Databricks secret or AZURE_OPENAI_API_KEY before running live AI.")
        findings, warnings = live_analysis(context, API_URL, MODEL, key, AUTH_TYPE, OUTPUT_LANGUAGE)
    if regulation and len(context["selected_regulation"]) < len(regulation.passages):
        warnings.append("Long regulation: only a keyword shortlist was sent to the model. Relevant provisions may be missed.")
    report = make_report(context, findings, warnings, mode, MODEL)
    report["input_fingerprint"] = fingerprint(claims_text, disclosure_text, regulation, mode, MODEL)
    return report


last_report = None
if WIDGETS_AVAILABLE:
    case_widget = widgets.Dropdown(options=[(c["name"], c["id"]) for c in CASES] + [("Custom material", "custom")],
                                   description="Case:", layout=widgets.Layout(width="95%"))
    mode_widget = widgets.Dropdown(options=["Offline demo", "Live AI"], description="Mode:")
    claims_widget = widgets.Textarea(value="\n".join(CASES[0]["claims"]), description="Claims:",
                                     layout=widgets.Layout(width="98%", height="130px"))
    disclosure_widget = widgets.Textarea(value=CASES[0]["disclosure"], description="Disclosure:",
                                         layout=widgets.Layout(width="98%", height="210px"))
    source_widget = widgets.Dropdown(options=["Fictional demo standard", "Upload regulation", "Workspace file", "No regulation"],
                                     description="Regulation:", layout=widgets.Layout(width="80%"))
    upload_widget = widgets.FileUpload(accept=".pdf,.txt,.md", multiple=False, description="Upload regulation")
    path_widget = widgets.Text(description="File path:", placeholder="/Workspace/Users/.../regulation.pdf",
                               layout=widgets.Layout(width="98%"))
    version_widget = widgets.Text(description="Version:", placeholder="User-provided version or effective date",
                                  layout=widgets.Layout(width="98%"))
    compare_button = widgets.Button(description="Compare & screen", button_style="success", icon="search")
    status_widget = widgets.HTML()
    output_widget = widgets.Output()

    def invalidate(change=None):
        global last_report
        last_report = None
        output_widget.clear_output()
        status_widget.value = "<small>Inputs changed. Click Compare &amp; screen to refresh findings.</small>"

    def change_case(change):
        case = next((c for c in CASES if c["id"] == change["new"]), None)
        claims_widget.value = "\n".join(case["claims"]) if case else ""
        disclosure_widget.value = case["disclosure"] if case else ""
        invalidate()

    def compare_clicked(button):
        global last_report
        compare_button.disabled = True
        last_report = None
        output_widget.clear_output()
        status_widget.value = "<b>Comparing claims and validating quotations…</b>"
        try:
            regulation = resolve_regulation(source_widget.value, version_widget.value,
                                             upload_widget.value, path_widget.value)
            last_report = run_review(claims_widget.value, disclosure_widget.value, regulation, mode_widget.value)
            with output_widget:
                display(HTML(render_report(last_report)))
            status_widget.value = "<b>Review ready.</b>"
        except (ValueError, OSError, ImportError) as exc:
            with output_widget:
                print(str(exc))
            status_widget.value = "<b>Analysis did not complete. Check the message below.</b>"
        except Exception:
            # Do not accidentally print credentials or provider payloads in shared notebook output.
            with output_widget:
                print("Unexpected response or environment error. Check the endpoint adapter and notebook setup.")
            status_widget.value = "<b>Analysis did not complete.</b>"
        finally:
            compare_button.disabled = False

    case_widget.observe(change_case, names="value")
    for widget in [claims_widget, disclosure_widget, source_widget, version_widget, path_widget, upload_widget, mode_widget]:
        widget.observe(invalidate, names="value")
    compare_button.on_click(compare_clicked)
    display(widgets.VBox([
        widgets.HTML("<h2>Green Claims Checker</h2><p>Comparison → Testing → Screening</p><p><b>Synthetic examples.</b> Offline demo replays authored findings. Live AI sends inputs to your configured Azure endpoint.</p>"),
        case_widget, mode_widget,
        widgets.HTML("<small>One claim per line. Edited/custom inputs require Live AI.</small>"),
        claims_widget, disclosure_widget, source_widget, upload_widget, path_widget, version_widget,
        widgets.HTML("<small>Upload regulation replaces the fictional standard. The app does not independently verify the latest version. If the upload button is unavailable, upload via Databricks and select Workspace file. TXT/MD require no extra parser; text PDFs require pypdf.</small>"),
        compare_button, status_widget, output_widget]))
else:
    print("ipywidgets is unavailable. Use the fallback cell below; no front-end package is required.")
