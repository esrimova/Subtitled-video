CSS = r"""
* {
    box-sizing: border-box;
}
body {
    margin: 0;
    padding: 24px;
    background: #101418;
    color: #e8edf2;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.5;
}
.container {
    width: 100%;
    margin: 0 auto;
}
h1 {
    margin: 0 0 16px;
    font-size: 1.5rem;
    font-weight: 600;
}
#player {
    display: grid;
    grid-template-columns: 68% 28%;
    column-gap: 4%;
    align-items: start;
}
#player:fullscreen {
    width: 100vw;
    height: 100vh;
    background: #000;
    padding: 2%;
    box-sizing: border-box;
    align-items: stretch;
}
#player:fullscreen #stage video {
    height: 100%;
    object-fit: contain;
}
#player:fullscreen #transcript {
    max-height: none;
}
#player:fullscreen #side {
    height: 100%;
    overflow: hidden;
}
#stage {
    width: 100%;
}
#stage video {
    width: 100%;
    display: block;
    background: #000;
}
#side {
    display: flex;
    flex-direction: column;
    min-width: 0;
}
#current-caption {
    position: relative;
    isolation: isolate;
    min-height: 3.5em;
    padding: 12px 16px;
    background: transparent;
    color: var(--sub-color, #ffffff);
    font-family: var(--sub-font, system-ui);
    font-size: var(--sub-size, 20px);
    font-weight: var(--sub-weight, 400);
    font-style: var(--sub-style, normal);
    text-align: center;
    border-radius: 8px;
    margin-bottom: 12px;
    overflow-wrap: anywhere;
}
#current-caption::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--sub-bg, #101418);
    filter: brightness(var(--sub-brightness, 1));
    border-radius: 8px;
    z-index: -1;
}
#controls {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
#controls button,
#controls select {
    padding: 8px 16px;
    background: #1e242b;
    color: #e8edf2;
    border: 1px solid #2d353d;
    border-radius: 6px;
    font-size: 0.9rem;
    cursor: pointer;
}
#controls button:hover,
#controls select:hover {
    background: #252d36;
    border-color: #3a444f;
}
#controls button:focus,
#controls select:focus {
    outline: 2px solid #4ea1ff;
    outline-offset: 2px;
}
#cc-toggle[aria-pressed="false"] {
    opacity: 0.5;
}
#transcript {
    flex: 1;
    max-height: 60vh;
    overflow-y: auto;
    border: 1px solid #2d353d;
    border-radius: 8px;
    background: #151a1f;
}
.line {
    display: flex;
    padding: 8px 12px;
    border-bottom: 1px solid #1e242b;
    cursor: pointer;
}
.line:last-child {
    border-bottom: none;
}
.line:hover {
    background: #1e242b;
}
.line.active {
    background: #1a222a;
    border-left: 3px solid #4ea1ff;
}
.line .ts {
    flex: 0 0 72px;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 0.8rem;
    color: #8b98a5;
    text-align: right;
    padding-right: 12px;
}
.line .tx {
    flex: 1;
    min-width: 0;
    word-break: break-word;
    font-family: var(--sub-font, system-ui);
    color: var(--sub-color, #ffffff);
    font-size: var(--sub-size, 20px);
    font-weight: var(--sub-weight, 400);
    font-style: var(--sub-style, normal);
}
#settings-panel[hidden] {
    display: none;
}
#settings-panel {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 8px 12px;
    padding: 12px;
    border: 1px solid #2d353d;
    border-radius: 8px;
    margin-bottom: 12px;
    background: #151a1f;
}
#settings-panel label {
    font-size: 0.9rem;
    color: #e8edf2;
}
#settings-panel select,
#settings-panel input[type="color"],
#settings-panel input[type="range"] {
    min-width: 0;
    width: 100%;
    background: #1e242b;
    color: #e8edf2;
    border: 1px solid #2d353d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.9rem;
}
#settings-panel input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: #4ea1ff;
}
#settings-panel button {
    grid-column: 1 / -1;
    padding: 8px 16px;
    background: #1e242b;
    color: #e8edf2;
    border: 1px solid #2d353d;
    border-radius: 6px;
    font-size: 0.9rem;
    cursor: pointer;
    margin-top: 4px;
}
#settings-panel button:hover {
    background: #252d36;
    border-color: #3a444f;
}
"""