from __future__ import annotations

from typing import Sequence, TypeVar

import streamlit as st

T = TypeVar("T")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap');

html, body, [data-testid="stAppViewContainer"] {
  font-family: 'DM Sans', sans-serif;
  background: radial-gradient(1200px 500px at 10% -10%, #d7ecf8 0%, transparent 55%),
              radial-gradient(900px 400px at 100% 0%, #e8f4fb 0%, transparent 50%),
              #F3F7FB;
}
.block-container { padding-top: 1rem; max-width: 1240px; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #00263d 0%, #014a73 100%);
}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
  color: #e7f4fc !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  padding: 8px 10px !important;
  margin-bottom: 6px;
}
[data-testid="stSidebar"] [data-baseweb="radio"] {
  background: transparent;
}

.hero {
  background: linear-gradient(120deg, #00263d 0%, #007AC2 62%, #5ec0ee 140%);
  border-radius: 22px;
  padding: 26px 30px 22px;
  color: #fff;
  margin-bottom: 1rem;
  box-shadow: 0 22px 50px rgba(0, 50, 77, 0.24);
  position: relative;
  overflow: hidden;
}
.hero:after {
  content: "";
  position: absolute; right: -40px; top: -50px;
  width: 220px; height: 220px; border-radius: 50%;
  background: rgba(255,255,255,0.08);
}
.hero h1 {
  font-family: Fraunces, Georgia, serif;
  font-size: 2.15rem; font-weight: 560; margin: 0 0 8px;
  letter-spacing: -0.03em;
}
.hero p { margin: 0; opacity: 0.93; max-width: 760px; font-size: 1.02rem; }
.pills { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,0.14);
  border: 1px solid rgba(255,255,255,0.28);
  border-radius: 999px; padding: 4px 11px; font-size: 0.74rem;
}
.kpi {
  background: #fff; border: 1px solid #d5e6f2; border-radius: 16px;
  padding: 14px 16px 12px; box-shadow: 0 10px 24px rgba(11,31,51,0.05);
}
.kpi .n { font-family: Fraunces, Georgia, serif; font-size: 1.75rem; color: #00324d; line-height: 1; }
.kpi .l { color: #5d7386; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 6px; }

.stepper { display: flex; gap: 6px; flex-wrap: wrap; margin: 4px 0 14px; }
.step {
  flex: 1; min-width: 120px; background: #fff; border: 1px solid #d5e6f2;
  border-radius: 12px; padding: 10px 12px; font-size: 0.8rem; color: #3d5568;
}
.step b { display: block; color: #007AC2; font-size: 0.7rem; letter-spacing: 0.08em; }
.acc-card, .ticket {
  background: #fff; border: 1px solid #d5e6f2; border-radius: 16px;
  padding: 14px 16px; margin-bottom: 10px;
  box-shadow: 0 8px 18px rgba(11,31,51,0.04);
}
.acc-card h4 { margin: 0 0 4px; font-size: 1.02rem; color: #0B1F33; }
.muted { color: #5d7386; font-size: 0.84rem; }
.badge { display: inline-block; border-radius: 6px; padding: 2px 8px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }
.badge-high { background: #d9f3e3; color: #0d6b3c; }
.badge-medium { background: #fff3d6; color: #8a5a00; }
.badge-low { background: #f1f4f7; color: #4a6072; }
.badge-ro { background: #e6f3fb; color: #007AC2; }
.badge-uf { background: #ece8fb; color: #5b3cc4; }
.draft-box {
  white-space: pre-wrap; font-size: 0.92rem; line-height: 1.5;
  background: #f6fbfe; border: 1px dashed #b7d3e6; border-radius: 12px; padding: 12px 14px;
}
.pagebar { color: #5d7386; font-size: 0.85rem; margin: 4px 0 10px; }
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def paginate(items: Sequence[T], *, key: str, page_size: int = 10) -> tuple[list[T], str]:
    total = len(items)
    pages = max(1, (total + page_size - 1) // page_size)
    sk = f"page_{key}"
    if sk not in st.session_state:
        st.session_state[sk] = 1
    page = int(st.session_state[sk])
    page = min(max(page, 1), pages)
    st.session_state[sk] = page
    c1, c2, c3, c4 = st.columns((1, 1, 2, 2))
    if c1.button("← Prev", key=f"{key}_prev", disabled=page <= 1):
        st.session_state[sk] = page - 1
        st.rerun()
    if c2.button("Next →", key=f"{key}_next", disabled=page >= pages):
        st.session_state[sk] = page + 1
        st.rerun()
    c3.caption(f"Page {page} of {pages}")
    c4.caption(f"{total} records · {page_size} / page")
    start = (page - 1) * page_size
    return list(items[start : start + page_size]), f'<div class="pagebar">Showing {start + 1 if total else 0}–{min(start + page_size, total)} of {total}</div>'


def stepper() -> None:
    st.markdown(
        """
<div class="stepper">
  <div class="step"><b>01 SIGNAL</b>New lead, cold account, meeting</div>
  <div class="step"><b>02 PREP</b>Research · ICP · Dayliff SKUs</div>
  <div class="step"><b>03 HUMAN GATE</b>Approve email / LinkedIn</div>
  <div class="step"><b>04 SIZE</b>Lab PDF → Economy / Standard / Premium</div>
  <div class="step"><b>05 QUOTE</b>BC BOQ + proposal in sizing</div>
</div>
""",
        unsafe_allow_html=True,
    )
