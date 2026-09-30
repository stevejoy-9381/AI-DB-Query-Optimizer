"""
scripts/capture_screenshots.py
Automated screenshot generator for MySQL Query Optimizer & Index Recommender documentation.
Uses Chrome DevTools Protocol (CDP) to drive the Streamlit app and capture high-resolution,
optimized screenshots and an animated walkthrough GIF.
"""

from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request

import websockets.sync.client as ws_sync
from PIL import Image

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


class CDPClient:
    def __init__(self, ws_url: str):
        self.ws = ws_sync.connect(ws_url, max_size=50 * 1024 * 1024)
        self.msg_id = 1

    def send(self, method: str, params: dict | None = None) -> dict:
        mid = self.msg_id
        self.msg_id += 1
        payload = {"id": mid, "method": method, "params": params or {}}
        self.ws.send(json.dumps(payload))
        while True:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == mid:
                if "error" in data:
                    raise RuntimeError(f"CDP Error: {data['error']}")
                return data.get("result", {})

    def evaluate(self, expression: str):
        res = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        return res.get("result", {}).get("value")

    def scroll_main(self, top_px: int):
        js = f"""
        (() => {{
            const main = document.querySelector('section.stMain');
            if (main) {{
                main.scrollTop = {top_px};
                return main.scrollTop;
            }}
            window.scrollTo(0, {top_px});
            return window.scrollY;
        }})()
        """
        return self.evaluate(js)

    def capture_screenshot(self, filepath: str, max_kb: int = 500) -> Image.Image:
        res = self.send("Page.captureScreenshot", {"format": "png"})
        png_data = base64.b64decode(res["data"])
        img = Image.open(io.BytesIO(png_data))

        # Save optimized PNG
        img.save(filepath, format="PNG", optimize=True)
        size_kb = os.path.getsize(filepath) / 1024
        print(
            f"Captured: {os.path.basename(filepath)} ({img.width}x{img.height}, {size_kb:.1f} KB)"
        )

        if size_kb > max_kb:
            img.save(filepath, format="PNG", optimize=True)
        return img

    def close(self):
        self.ws.close()


def run_capture_pipeline():
    sample_sql = (
        "SELECT * FROM orders "
        "WHERE customer_id IN (SELECT customer_id FROM customers WHERE status = 'inactive') "
        "AND YEAR(order_date) = 2024 "
        "ORDER BY order_date DESC;"
    )
    encoded_query = urllib.parse.quote(sample_sql)
    target_url = f"http://localhost:8501/?query={encoded_query}&auto_analyze=1"

    print("Starting headless browser for screenshot capture...")
    proc = subprocess.Popen(
        [
            CHROME_PATH,
            "--headless=new",
            "--remote-debugging-port=9222",
            "--user-data-dir=C:/Users/steve/AppData/Local/Temp/chrome_ss_profile10",
            "--window-size=1366,880",
            "--hide-scrollbars",
            "--disable-gpu",
            "--no-first-run",
            target_url,
        ]
    )

    gif_frames = []

    try:
        time.sleep(3)
        targets = json.loads(urllib.request.urlopen("http://localhost:9222/json").read())
        page_target = next(t for t in targets if t.get("type") == "page")
        client = CDPClient(page_target["webSocketDebuggerUrl"])

        client.send("Page.enable")
        client.send("DOM.enable")

        print("Waiting for Streamlit app to load and complete analysis...")
        for _ in range(35):
            time.sleep(1)
            loaded = client.evaluate(
                "Boolean(document.querySelector('.score-card-val') || document.body.innerText.includes('Score Breakdown') || document.body.innerText.includes('Optimization Strategies'))"
            )
            if loaded:
                break
        time.sleep(3)

        # 1. Capture initial overview (Offline Demo Mode banner & Query Input)
        print("Capturing 01_app_overview.png...")
        client.scroll_main(0)
        time.sleep(1.5)
        frame1 = client.capture_screenshot(os.path.join(OUTPUT_DIR, "01_app_overview.png"))
        gif_frames.append(frame1)

        # 2. Capture Query Analysis Dashboard & Score Gauge
        print("Capturing 02_query_analysis_dashboard.png...")
        client.scroll_main(380)
        time.sleep(1.5)
        frame2 = client.capture_screenshot(
            os.path.join(OUTPUT_DIR, "02_query_analysis_dashboard.png")
        )
        gif_frames.append(frame2)

        # 3. Capture Detected Anti-patterns & Index Recommendations
        print("Capturing 03_antipattern_findings_and_index_advice.png...")
        client.scroll_main(880)
        time.sleep(1.5)
        frame3 = client.capture_screenshot(
            os.path.join(OUTPUT_DIR, "03_antipattern_findings_and_index_advice.png")
        )
        gif_frames.append(frame3)

        # 4. Switch to "🔬 Advanced Analysis" Tab
        print("Switching to Advanced Analysis tab...")
        click_adv_tab_js = """
        (() => {
            const tabs = Array.from(document.querySelectorAll('button[role="tab"]'));
            const adv = tabs.find(t => t.innerText.includes('Advanced Analysis'));
            if (adv) {
                adv.click();
                return true;
            }
            return false;
        })()
        """
        client.evaluate(click_adv_tab_js)
        time.sleep(3)

        # 5. Capture Execution Plan Visualizer (Plotly Tree)
        print("Capturing 04_execution_plan_visualizer.png...")
        client.scroll_main(280)
        time.sleep(2)
        frame4 = client.capture_screenshot(
            os.path.join(OUTPUT_DIR, "04_execution_plan_visualizer.png")
        )
        gif_frames.append(frame4)

        # 6. Scroll to Index Impact Simulator
        print("Capturing 05_index_impact_simulator.png...")
        client.scroll_main(1180)
        time.sleep(2)
        frame5 = client.capture_screenshot(
            os.path.join(OUTPUT_DIR, "05_index_impact_simulator.png")
        )
        gif_frames.append(frame5)

        # 7. Scroll to Side-by-Side Rewrite Diff View
        print("Capturing 06_rewrite_side_by_side_diff.png...")
        client.scroll_main(1950)
        time.sleep(2)
        frame6 = client.capture_screenshot(
            os.path.join(OUTPUT_DIR, "06_rewrite_side_by_side_diff.png")
        )
        gif_frames.append(frame6)

        # 8. Switch to "📜 Query History" Tab
        print("Switching to Query History tab...")
        click_hist_tab_js = """
        (() => {
            const tabs = Array.from(document.querySelectorAll('button[role="tab"]'));
            const hist = tabs.find(t => t.innerText.includes('Query History'));
            if (hist) {
                hist.click();
                return true;
            }
            return false;
        })()
        """
        client.evaluate(click_hist_tab_js)
        time.sleep(3)
        client.scroll_main(0)
        time.sleep(1.5)

        print("Capturing 07_persistent_query_history.png...")
        frame7 = client.capture_screenshot(
            os.path.join(OUTPUT_DIR, "07_persistent_query_history.png")
        )
        gif_frames.append(frame7)

        # 9. Create animated walkthrough GIF
        print("Assembling demo walkthrough GIF (docs/screenshots/demo_walkthrough.gif)...")
        gif_path = os.path.join(OUTPUT_DIR, "demo_walkthrough.gif")

        resized_frames = []
        for f in [frame1, frame2, frame3, frame4, frame5, frame6, frame7]:
            rf = f.resize((960, int(960 * f.height / f.width)), Image.Resampling.LANCZOS)
            rf = rf.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
            resized_frames.append(rf)

        if resized_frames:
            resized_frames[0].save(
                gif_path,
                save_all=True,
                append_images=resized_frames[1:],
                duration=1800,  # 1.8s per frame
                loop=0,
                optimize=True,
            )
            gif_size_kb = os.path.getsize(gif_path) / 1024
            print(f"Created GIF: demo_walkthrough.gif ({gif_size_kb:.1f} KB)")

        client.close()
        print("All screenshots and GIF generation completed successfully!")

    finally:
        proc.terminate()


if __name__ == "__main__":
    run_capture_pipeline()
