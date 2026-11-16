from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = [
    ROOT / "src/static/index.html",
    ROOT / "src/static/app-selection.html",
    ROOT / "src/static/dashboard.html",
    ROOT / "src/static/thank-you.html",
]

def main():
    for html_path in HTML_FILES:
        source = html_path.read_text(encoding="utf-8")
        scripts = []
        marker = "<script"
        cursor = 0
        while True:
            start = source.find(marker, cursor)
            if start < 0:
                break
            tag_end = source.find(">", start)
            end = source.find("</script>", tag_end)
            if tag_end < 0 or end < 0:
                raise SystemExit(f"Unclosed script tag in {html_path}")
            tag = source[start:tag_end + 1]
            if "src=" not in tag:
                scripts.append(source[tag_end + 1:end])
            cursor = end + len("</script>")
        for index, script in enumerate(scripts, start=1):
            result = subprocess.run(
                ["node", "--check"],
                input=script,
                text=True,
                capture_output=True,
            )
            if result.returncode:
                print(f"JavaScript syntax error in {html_path} inline script {index}:")
                print(result.stderr)
                return result.returncode
        print(f"Checked {html_path.relative_to(ROOT)} ({len(scripts)} inline scripts)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
