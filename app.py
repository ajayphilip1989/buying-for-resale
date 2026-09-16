"""
Basics of Purchasing — in-class response app
Lecture 16.

Three roles, chosen in the sidebar:
  Student    — no password. Nickname once, then answer what is open.
  Projector  — password. Big screen at the front. No controls.
  Instructor — password. Opens and closes questions, reveals results, CSV.

Responses live in server memory and are mirrored to responses.json, so
refreshes, logouts and reconnects cost nothing. A container restart is
the only exposure — download the CSV after each question.
"""

import csv
import io
import json
import os
import threading
from collections import Counter
from datetime import datetime, timezone, timedelta

import streamlit as st

IST = timezone(timedelta(hours=5, minutes=30))
STORE = "responses.json"

PROJECTOR_PW = "sanjana2026"      # change before class
INSTRUCTOR_PW = "prateeka2026"    # change before class

QUESTIONS = {
    "q1": {
        "label": "Q1 — word cloud",
        "prompt": "In one or two words: what would you look at to decide "
                  "which brands to keep, and how much of each?",
        "type": "words",
        "help": "Up to three entries, separated by commas. An entry can be two words, e.g. shelf space",
    },
    "q2": {
        "label": "Q2 — best use of space",
        "prompt": "Which item is making the best use of the space it occupies?",
        "type": "single",
        "options": ["Item A", "Item B", "Item C"],
    },
    "q3": {
        "label": "Q3 — own label",
        "prompt": "For which of these would a shop's own label work?",
        "type": "multi",
        "options": ["Sugar", "A cola", "Detergent powder", "Toor dal"],
    },
}

HEADER = ["timestamp_ist", "question", "nickname", "answer"]
INK, BLUE, GREEN, AMBER, SLATE = "#16303F", "#2E7CA8", "#00875A", "#BE7B12", "#5C7288"


# --------------------------------------------------------------------------
# shared state
# --------------------------------------------------------------------------

@st.cache_resource
def state():
    s = {
        "open": None,        # question accepting answers
        "project": None,     # question shown on the projector
        "reveal": False,     # show the distribution, or just a count
        "rows": [],
        "answered": set(),
        "lock": threading.Lock(),
    }
    if os.path.exists(STORE):
        try:
            with open(STORE) as fh:
                s["rows"] = json.load(fh)
            s["answered"] = {(r[2].strip().lower(), r[1]) for r in s["rows"]}
        except Exception:
            pass
    return s


def persist():
    try:
        with open(STORE, "w") as fh:
            json.dump(state()["rows"], fh)
    except Exception:
        pass


def record(qid, nickname, answer):
    s = state()
    row = [datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"), qid, nickname, answer]
    with s["lock"]:
        s["rows"].append(row)
        s["answered"].add((nickname.strip().lower(), qid))
    persist()


def answers_for(qid):
    return [r[3] for r in state()["rows"] if r[1] == qid]


# --------------------------------------------------------------------------
# word handling
# --------------------------------------------------------------------------

STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "is", "it", "for",
        "on", "by", "how", "much", "what"}

FOLD = {"sales": "sale", "prices": "price", "brands": "brand", "costs": "cost",
        "customers": "customer", "margins": "margin", "profits": "profit",
        "stocks": "stock", "inventory": "stock", "demands": "demand",
        "expiry": "expiry date", "shelflife": "shelf life", "spaces": "space",
        "shelves": "shelf", "discounts": "discount", "suppliers": "supplier"}


def normalise(word):
    w = "".join(c for c in word.lower() if c.isalnum() or c == " ").strip()
    return FOLD.get(w, w)


def word_counts(qid):
    words = []
    for a in answers_for(qid):
        words += [x.strip() for x in a.split(",")]
    return Counter(w for w in words if w and w not in STOP)


def cloud_html(counts, scale=1.0):
    if not counts:
        return f"<p style='color:{SLATE};text-align:center'>No responses yet.</p>"
    top = counts.most_common(40)
    hi = top[0][1]
    palette = [INK, BLUE, GREEN, AMBER, SLATE]
    spans = []
    for i, (w, n) in enumerate(top):
        size = int((16 + 46 * (n / hi) ** 0.7) * scale)
        spans.append(f"<span style='font-size:{size}px;color:{palette[i % 5]};"
                     f"margin:{int(8*scale)}px {int(16*scale)}px;display:inline-block;"
                     f"font-weight:600;font-family:Calibri,sans-serif'>{w}</span>")
    return ("<div style='text-align:center;line-height:1.4;padding:20px'>"
            + "".join(spans) + "</div>")


def option_counts(qid):
    counts = Counter()
    for a in answers_for(qid):
        for part in a.split(";"):
            counts[part.strip()] += 1
    return counts


def bars_html(qid, big=False):
    q = QUESTIONS[qid]
    counts = option_counts(qid)
    total = len(answers_for(qid)) or 1
    fs = 34 if big else 18
    h = 34 if big else 20
    out = []
    for i, opt in enumerate(q["options"]):
        n = counts.get(opt, 0)
        pct = 100 * n / total
        colour = [BLUE, GREEN, AMBER, SLATE][i % 4]
        out.append(
            f"<div style='margin:{h//2}px 0;font-family:Calibri,sans-serif'>"
            f"<div style='font-size:{fs}px;color:{INK};font-weight:600'>{opt} "
            f"<span style='color:{SLATE};font-weight:400'>&nbsp;{n}</span></div>"
            f"<div style='background:#EEF3F7;border-radius:6px;height:{h}px;width:100%'>"
            f"<div style='background:{colour};height:{h}px;width:{pct:.1f}%;"
            f"border-radius:6px'></div></div></div>")
    return "<div style='padding:10px 40px'>" + "".join(out) + "</div>"


# --------------------------------------------------------------------------
# student
# --------------------------------------------------------------------------

def student_view():
    st.title("Basics of Purchasing")

    # the nickname lives in the URL, so a refresh or a reconnect keeps it
    if "nickname" not in st.session_state:
        from_url = st.query_params.get("me", "").strip()
        if from_url:
            st.session_state["nickname"] = from_url

    if "nickname" not in st.session_state:
        st.write("Enter your nickname in the usual format to begin.")
        name = st.text_input("Nickname", max_chars=40)
        if st.button("Start", type="primary"):
            if name.strip():
                st.session_state["nickname"] = name.strip()
                st.query_params["me"] = name.strip()
                st.rerun()
            else:
                st.warning("Please enter a nickname.")
        return

    left, right = st.columns([5, 1])
    left.caption(f"Signed in as {st.session_state['nickname']}")
    if right.button("Not you?"):
        st.session_state.pop("nickname", None)
        st.query_params.clear()
        st.rerun()
    answer_panel()


@st.fragment(run_every="3s")
def answer_panel():
    s = state()
    qid = s["open"]
    nick = st.session_state["nickname"]

    if qid is None:
        st.info("Waiting for the next question.")
        return
    if (nick.strip().lower(), qid) in s["answered"]:
        st.success("Your answer has been recorded. Waiting for the next question.")
        return

    q = QUESTIONS[qid]
    st.subheader(q["prompt"])

    if q["type"] == "words":
        text = st.text_input(q.get("help", ""), max_chars=70, key=f"in_{qid}")
        if st.button("Send", type="primary", key=f"b_{qid}"):
            words = [normalise(w) for w in text.split(",")]
            words = [w for w in words if w][:3]
            if words:
                record(qid, nick, ", ".join(words))
                st.rerun(scope="fragment")
            else:
                st.warning("Type at least one word.")

    elif q["type"] == "single":
        choice = st.radio("Choose one", q["options"], index=None, key=f"in_{qid}")
        if st.button("Send", type="primary", key=f"b_{qid}"):
            if choice:
                record(qid, nick, choice)
                st.rerun(scope="fragment")
            else:
                st.warning("Pick one option.")

    else:
        picked = [o for o in q["options"] if st.checkbox(o, key=f"in_{qid}_{o}")]
        if st.button("Send", type="primary", key=f"b_{qid}"):
            if picked:
                record(qid, nick, "; ".join(picked))
                st.rerun(scope="fragment")
            else:
                st.warning("Tick at least one.")


# --------------------------------------------------------------------------
# projector
# --------------------------------------------------------------------------

@st.fragment(run_every="2s")
def projector_view():
    s = state()
    qid = s["project"] or s["open"]

    if qid is None:
        st.markdown(
            f"<div style='text-align:center;padding-top:120px;font-family:Calibri,sans-serif'>"
            f"<div style='font-size:46px;color:{INK};font-weight:700'>Basics of Purchasing</div>"
            f"<div style='font-size:24px;color:{SLATE};margin-top:14px'>Buying for resale</div>"
            "</div>", unsafe_allow_html=True)
        return

    q = QUESTIONS[qid]
    n = len(answers_for(qid))

    st.markdown(
        f"<div style='font-size:30px;color:{INK};font-weight:700;"
        f"font-family:Calibri,sans-serif;padding:6px 30px 0'>{q['prompt']}</div>",
        unsafe_allow_html=True)

    if not s["reveal"]:
        st.markdown(
            f"<div style='text-align:center;padding-top:90px;font-family:Calibri,sans-serif'>"
            f"<div style='font-size:96px;color:{BLUE};font-weight:700'>{n}</div>"
            f"<div style='font-size:26px;color:{SLATE}'>responses received</div>"
            "</div>", unsafe_allow_html=True)
        return

    if q["type"] == "words":
        st.markdown(cloud_html(word_counts(qid), scale=1.5), unsafe_allow_html=True)
    else:
        st.markdown(bars_html(qid, big=True), unsafe_allow_html=True)
    st.markdown(
        f"<div style='text-align:center;color:{SLATE};font-size:20px;"
        f"font-family:Calibri,sans-serif'>{n} responses</div>",
        unsafe_allow_html=True)


# --------------------------------------------------------------------------
# instructor
# --------------------------------------------------------------------------

def instructor_view():
    st.title("Instructor panel")
    s = state()

    st.write("**Accepting answers**")
    cols = st.columns(len(QUESTIONS) + 1)
    for i, (qid, q) in enumerate(QUESTIONS.items()):
        live = s["open"] == qid
        if cols[i].button(("Close " if live else "Open ") + q["label"],
                          type="primary" if live else "secondary",
                          use_container_width=True):
            s["open"] = None if live else qid
            if not live:
                s["project"], s["reveal"] = qid, False
            st.rerun()
    if cols[-1].button("Close all", use_container_width=True):
        s["open"] = None
        st.rerun()

    st.write("**On the projector**")
    pcols = st.columns(len(QUESTIONS) + 2)
    for i, (qid, q) in enumerate(QUESTIONS.items()):
        shown = s["project"] == qid
        if pcols[i].button(("Showing " if shown else "Show ") + q["label"],
                           type="primary" if shown else "secondary",
                           use_container_width=True):
            s["project"] = qid
            st.rerun()
    if pcols[-2].button("Blank screen", use_container_width=True):
        s["project"], s["reveal"] = None, False
        st.rerun()
    if pcols[-1].button("Hide results" if s["reveal"] else "REVEAL results",
                        type="secondary" if s["reveal"] else "primary",
                        use_container_width=True):
        s["reveal"] = not s["reveal"]
        st.rerun()

    st.caption(
        f"Open: {QUESTIONS[s['open']]['label'] if s['open'] else 'none'}  |  "
        f"Projector: {QUESTIONS[s['project']]['label'] if s['project'] else 'blank'}  |  "
        f"Results: {'revealed' if s['reveal'] else 'hidden'}")

    st.divider()
    monitor()
    st.divider()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    w.writerows(s["rows"])
    st.download_button("Download responses (CSV)", buf.getvalue(),
                       file_name="lecture16_responses.csv", mime="text/csv",
                       type="primary", use_container_width=True)
    st.caption(f"{len(s['rows'])} response(s) held.")


@st.fragment(run_every="3s")
def monitor():
    tabs = st.tabs([q["label"] for q in QUESTIONS.values()])
    for tab, (qid, q) in zip(tabs, QUESTIONS.items()):
        with tab:
            data = answers_for(qid)
            st.caption(f"{len(data)} response(s)")
            if q["type"] == "words":
                st.markdown(cloud_html(word_counts(qid)), unsafe_allow_html=True)
            else:
                st.markdown(bars_html(qid), unsafe_allow_html=True)


# --------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Basics of Purchasing", page_icon="🛒",
                       layout="wide")
    role = st.sidebar.radio("Role", ["Student", "Projector", "Instructor"])

    if role == "Student":
        st.sidebar.caption("No password needed.")
        student_view()
        return

    pw = st.sidebar.text_input("Password", type="password")
    if role == "Projector":
        if pw == PROJECTOR_PW:
            st.sidebar.success("Projector mode")
            projector_view()
        else:
            st.info("Enter the projector password in the sidebar.")
    else:
        if pw == INSTRUCTOR_PW:
            st.sidebar.success("Instructor mode")
            instructor_view()
        else:
            st.info("Enter the instructor password in the sidebar.")


main()
