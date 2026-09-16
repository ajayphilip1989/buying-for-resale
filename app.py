"""
Basics of Purchasing — in-class response app
Lecture 16.

No external accounts needed. Responses are held in memory, mirrored to
responses.json on the container after every submission, and downloadable
as CSV at any time.

Optional: if FORM_POST_URL and FIELD_IDS are filled in below, every response
is also posted to a Google Form, which writes it to that Form's linked Sheet.
Leave them blank and the app works exactly the same without it.
"""

import csv
import io
import json
import os
import threading
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta

import streamlit as st

IST = timezone(timedelta(hours=5, minutes=30))
STORE = "responses.json"

# --- optional Google Form mirror (leave blank to skip) ---------------------
FORM_POST_URL = ""       # .../formResponse
FIELD_IDS = {            # entry.XXXXXXX ids from the form
    "timestamp": "",
    "question": "",
    "nickname": "",
    "answer": "",
}

# --------------------------------------------------------------------------

QUESTIONS = {
    "q1": {
        "label": "Q1 — word cloud",
        "prompt": "In one or two words: what would you look at to decide "
                  "which brands to keep, and how much of each?",
        "type": "words",
        "help": "Up to three words. Separate them with spaces or commas.",
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
ADMIN_CODE = "shelf2026"          # change this before class


@st.cache_resource
def state():
    s = {
        "open": None,
        "rows": [],
        "answered": set(),
        "lock": threading.Lock(),
    }
    if os.path.exists(STORE):                       # survive a restart
        try:
            with open(STORE) as fh:
                s["rows"] = json.load(fh)
            s["answered"] = {(r[2].strip().lower(), r[1]) for r in s["rows"]}
        except Exception:
            pass
    return s


def persist():
    s = state()
    try:
        with open(STORE, "w") as fh:
            json.dump(s["rows"], fh)
    except Exception:
        pass


def mirror_to_form(row):
    if not FORM_POST_URL or not FIELD_IDS.get("answer"):
        return
    try:
        data = urllib.parse.urlencode({
            FIELD_IDS["timestamp"]: row[0],
            FIELD_IDS["question"]: row[1],
            FIELD_IDS["nickname"]: row[2],
            FIELD_IDS["answer"]: row[3],
        }).encode()
        urllib.request.urlopen(FORM_POST_URL, data=data, timeout=4)
    except Exception:
        pass


def record(qid, nickname, answer):
    s = state()
    row = [datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"), qid, nickname, answer]
    with s["lock"]:
        s["rows"].append(row)
        s["answered"].add((nickname.strip().lower(), qid))
    persist()
    mirror_to_form(row)


def answers_for(qid):
    return [r[3] for r in state()["rows"] if r[1] == qid]


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


def cloud_html(words):
    counts = Counter(w for w in words if w and w not in STOP)
    if not counts:
        return "<p style='color:#6B8194'>No responses yet.</p>"
    top = counts.most_common(40)
    hi = top[0][1]
    palette = ["#16303F", "#2E7CA8", "#00875A", "#BE7B12", "#5C7288"]
    spans = []
    for i, (w, n) in enumerate(top):
        size = 16 + int(46 * (n / hi) ** 0.7)
        spans.append(f"<span style='font-size:{size}px;color:{palette[i % 5]};"
                     f"margin:6px 14px;display:inline-block;font-weight:600;"
                     f"font-family:Calibri,sans-serif' title='{n}'>{w}</span>")
    return ("<div style='text-align:center;line-height:1.5;padding:18px'>"
            + "".join(spans) + "</div>")


# --------------------------------------------------------------------------

def student_view():
    st.title("Basics of Purchasing")
    if "nickname" not in st.session_state:
        st.write("Enter your nickname in the usual format to begin.")
        name = st.text_input("Nickname", max_chars=40)
        if st.button("Start", type="primary"):
            if name.strip():
                st.session_state["nickname"] = name.strip()
                st.rerun()
            else:
                st.warning("Please enter a nickname.")
        return
    st.caption(f"Signed in as {st.session_state['nickname']}")
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
        text = st.text_input(q.get("help", ""), max_chars=60, key=f"in_{qid}")
        if st.button("Send", type="primary", key=f"b_{qid}"):
            words = [normalise(w) for w in text.replace(",", " ").split()]
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

def admin_view():
    st.title("Instructor panel")
    s = state()

    cols = st.columns(len(QUESTIONS) + 1)
    for i, (qid, q) in enumerate(QUESTIONS.items()):
        live = s["open"] == qid
        if cols[i].button(("Close " if live else "Open ") + q["label"],
                          type="primary" if live else "secondary",
                          use_container_width=True):
            s["open"] = None if live else qid
            st.rerun()
    if cols[-1].button("Close all", use_container_width=True):
        s["open"] = None
        st.rerun()

    st.divider()
    live_panel()
    st.divider()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    w.writerows(s["rows"])
    st.download_button("Download responses (CSV)", buf.getvalue(),
                       file_name="lecture16_responses.csv", mime="text/csv",
                       type="primary", use_container_width=True)
    st.caption(f"{len(s['rows'])} response(s) held. Saved to disk after every submission.")


@st.fragment(run_every="3s")
def live_panel():
    s = state()
    st.caption("Open question: " +
               (QUESTIONS[s["open"]]["label"] if s["open"] else "none"))
    tabs = st.tabs([q["label"] for q in QUESTIONS.values()])
    for tab, (tid, q) in zip(tabs, QUESTIONS.items()):
        with tab:
            data = answers_for(tid)
            st.caption(f"{len(data)} response(s)")
            if q["type"] == "words":
                words = []
                for a in data:
                    words += [x.strip() for x in a.split(",")]
                st.markdown(cloud_html(words), unsafe_allow_html=True)
            else:
                counts = Counter()
                for a in data:
                    for part in a.split(";"):
                        counts[part.strip()] += 1
                for opt in q["options"]:
                    n = counts.get(opt, 0)
                    st.write(f"**{opt}** — {n}")
                    st.progress(min(n / len(data), 1.0) if data else 0.0)


def main():
    st.set_page_config(page_title="Basics of Purchasing", page_icon="🛒")
    if st.query_params.get("admin") == ADMIN_CODE:
        admin_view()
    else:
        student_view()


main()
