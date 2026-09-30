# Demo Recording Guide (15–30 Second Video / GIF Walkthrough)

This guide provides a standardized script and recommended tooling for recording crisp, authentic 15–30 second demonstration clips of the **Rule-Based SQL Query Optimizer & Index Recommender**.

---

## 🎥 Recommended Tooling
- **Windows / Mac / Linux:** [ScreenToGif](https://www.screentogif.com/) (Open-source, lightweight GIF & MP4 recorder with frame editor)
- **Cross-Platform:** [OBS Studio](https://obsproject.com/) (Lossless 1080p recording, exportable to MP4 or WebM)
- **Mac:** [LICEcap](https://www.cockos.com/licecap/) or QuickTime Player screen recording

---

## ⚙️ Preparation & Setup
1. **Resolution & Theme:**
   - Set browser window dimensions to `1366 x 880` (or 16:9 aspect ratio at `1280 x 720`).
   - Use standard browser zoom (`100%`).
   - Default dark theme is active by default in `.streamlit/config.toml`.
2. **Start the Application:**
   ```bash
   streamlit run app.py
   ```
3. **Open the Local URL:**
   ```
   http://localhost:8501
   ```

---

## ⏱️ Step-by-Step 20-Second Recording Script

| Timestamp | Screen / Action | What to Showcase |
|---|---|---|
| **0:00 – 0:04** | **Landing & Empty State** | Show the dashboard header, offline demo banner ("Offline estimates only"), and click **"📂 Load Sample Query"** in the sidebar or one of the quick sample cards (e.g. `Sample: Unindexed JOIN`). |
| **0:04 – 0:08** | **Analysis & Health Score** | Click **"⚡ Analyze Query"**. Show spinner progress, the health score gauge (e.g. `75 / 100`), complexity indicator (`Complex`), and the waterfall **Explainable Score Breakdown**. |
| **0:08 – 0:13** | **Plan & Index Recommendations** | Click the **"🔬 Advanced Analysis"** tab. Highlight the simulated MySQL EXPLAIN tree with access types (`ALL`, `range`, `filesort`), followed by the **Index Impact Simulator** (+25 score gain, estimated speedup). |
| **0:13 – 0:17** | **Side-by-Side Rewrite Diff** | Scroll down to the **Query Rewrite Engine**. Highlight the side-by-side AST SQL diff showing amber deletions (`SELECT *`) and green replacements with explicit columns and date range syntax. Point out the semantic safety badge (`Verified equivalent` or `Changes results`). |
| **0:17 – 0:20** | **Persistent History** | Switch to the **"📜 Query History"** tab. Demonstrate the SQLite-persisted query runs, score range filter, and comparison dropdown. |

---

## 💾 GIF Optimization Guidelines
- **Target File Size:** Keep the final GIF under **1 MB** (or under 500 KB for direct Git hosting).
- **Framerate:** 12–15 FPS is optimal for UI demonstrations.
- **Palette:** 128 colors with Floyd-Steinberg or adaptive diffusion dithering.
- **Automated Capture:** You can also run the bundled headless capture tool:
  ```bash
  python scripts/capture_screenshots.py
  ```
