"""Start the Gmail based INCEPT legal intake workspace."""
import os
from pathlib import Path

os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    import gradio as gr
    from scripts.workspace_ui import build_workspace_app

    app = build_workspace_app()
    app.launch(
        server_name='127.0.0.1',
        server_port=int(os.getenv('INCEPT_GRADIO_PORT', '7860')),
        share=False,
        inbrowser=False,
        show_error=False,
        theme=gr.themes.Soft(font=['Arial', 'sans-serif']),
        footer_links=[],
        allowed_paths=[str(Path(__file__).resolve().parents[1] / 'downloads')],
        blocked_paths=[str(Path(__file__).resolve().parents[1] / '.env')],
    )


if __name__ == '__main__':
    main()
