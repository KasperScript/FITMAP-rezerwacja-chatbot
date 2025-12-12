import json
import re
import streamlit as st
import streamlit.components.v1 as components

from db_loader import load_availability
from agent import handle_user_query
from reservations import add_reservation, load_reservations


@st.cache_data
def get_db():
    return load_availability()


db_json = get_db()

st.set_page_config(page_title="Sport AI Agent", page_icon="⚽")
st.title("Sport AI Agent")
st.caption("Prosty agent do wyszukiwania obiektów sportowych na bazie Gemini 2.5 Flash i pliku dostepnosc.json")


if "messages" not in st.session_state:
    st.session_state["messages"] = []  
if "last_options" not in st.session_state:
    st.session_state["last_options"] = []
if "last_query" not in st.session_state:
    st.session_state["last_query"] = ""
if "scroll_to_top" not in st.session_state:
    st.session_state["scroll_to_top"] = False
if "last_filters" not in st.session_state:
    st.session_state["last_filters"] = None



for msg in st.session_state["messages"]:
    content = msg.get("content")
    if not isinstance(content, str):
        continue
    content = content.strip()
    if not content or content.lower() == "undefined":
        continue
    with st.chat_message(msg["role"]):
        st.markdown(content)



user_input = st.chat_input("Napisz, czego szukasz (np. joga po 18, do 100 zł, w Warszawie)...")

if user_input:
    
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    
    result = handle_user_query(user_input, db_json, st.session_state.get("last_filters"))
    raw_answer = result["raw_answer"]
    payload = result["parsed_payload"]
    st.session_state["last_filters"] = result.get("filters")

    
    assistant_text = raw_answer if isinstance(raw_answer, str) else ""
    if assistant_text:
        assistant_text = re.sub(r"```json.*?```", "", assistant_text, flags=re.DOTALL | re.IGNORECASE)
        lines = [line for line in assistant_text.splitlines() if line.strip().lower() != "undefined"]
        assistant_text = "\n".join(lines).strip()
        if assistant_text:
            lines = assistant_text.splitlines()
            cut_idx = None
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped[0] in "{[,}]":
                    cut_idx = i
                    break
                if stripped[0] in "\"'" and ('":' in stripped or "':" in stripped):
                    cut_idx = i
                    break
            if cut_idx is not None:
                assistant_text = "\n".join(lines[:cut_idx]).strip()

    
    if assistant_text:
        with st.chat_message("assistant"):
            st.markdown(assistant_text)

    if payload:
        options = payload.get("options", [])
        st.session_state["last_options"] = options
        st.session_state["last_query"] = user_input

    if assistant_text:
        st.session_state["messages"].append({"role": "assistant", "content": assistant_text})
    st.session_state["scroll_to_top"] = True

st.markdown("---")
st.subheader("Rezerwacja")

last_options = st.session_state.get("last_options") or []
if last_options:
    labels = []
    for opt in last_options:
        obj_id = opt.get("object_id")
        name = opt.get("object_name") or "brak nazwy"
        city = opt.get("city") or "brak miasta"
        date = opt.get("date") or "brak daty"
        time_range = opt.get("time_range") or "brak godzin"
        price = opt.get("price_per_hour")
        price_str = f"{price} zł/h" if price is not None else "brak ceny"
        labels.append(f"{obj_id} | {name} | {city} | {date} {time_range} | {price_str}")

    selected_label = st.selectbox("Wybierz opcję", labels)
    selected_idx = labels.index(selected_label)
    selected_option = last_options[selected_idx]

    customer_name = st.text_input("Imię i nazwisko")
    customer_email = st.text_input("Email")

    if st.button("Rezerwuj"):
        if not customer_name.strip() or not customer_email.strip():
            st.warning("Podaj imię i nazwisko oraz email.")
        else:
            reservation = add_reservation(
                selected_option,
                customer_name.strip(),
                customer_email.strip(),
                st.session_state.get("last_query", ""),
            )
            st.success(
                "Rezerwacja zapisana. "
                f"ID: {reservation['id']} | "
                f"{reservation.get('object_name', 'brak nazwy')} | "
                f"{reservation.get('date', 'brak daty')} | "
                f"{reservation.get('time_range', 'brak godzin')} | "
                f"{reservation.get('price_per_hour', 'brak ceny')} zł/h"
            )
else:
    st.info("Najpierw wyszukaj opcje, aby zarezerwować.")

st.subheader("Ostatnie rezerwacje")
limit = st.number_input("Liczba rezerwacji do pokazania", min_value=1, max_value=20, value=5, step=1)
reservations = load_reservations()
if reservations:
    recent = reservations[-int(limit):]
    rows = []
    for r in reversed(recent):
        rows.append(
            {
                "id": r.get("id"),
                "object_name": r.get("object_name"),
                "date": r.get("date"),
                "time_range": r.get("time_range"),
                "price_per_hour": r.get("price_per_hour"),
                "customer_name": r.get("customer_name"),
            }
        )
    st.table(rows)
else:
    st.info("Brak rezerwacji.")

if st.session_state.get("scroll_to_top"):
    components.html(
        "<script>"
        "const goTop=()=>{window.scrollTo(0,0);document.documentElement.scrollTop=0;document.body.scrollTop=0;};"
        "setTimeout(goTop,0);setTimeout(goTop,150);setTimeout(goTop,400);"
        "</script>",
        height=0,
    )
    st.session_state["scroll_to_top"] = False
