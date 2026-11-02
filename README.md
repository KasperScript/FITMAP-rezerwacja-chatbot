# FITMAP reservation chatbot prototype

A local Streamlit demo searches the static `dostepnosc.json` sports venue dataset
using Gemini and records demo bookings in `rezerwacje.json`. It has no connection
to venue booking systems. Included dates and availability are sample data and may
be historical. A saved booking is not a real venue confirmation.

## Run locally

Use Python 3.10+ in a virtual environment:

```sh
python -m pip install -r requirements.txt
streamlit run app.py
```

Set `GEMINI_API_KEY` in the process environment before starting (load it from your
shared secret store). Gemini requests require network access and may incur costs.
Do not commit credentials or real customer details.

## Offline checks

```sh
python -m unittest discover -s tests -v
python -m compileall -q app.py reservations.py
```

Bookings reject overlapping times for the same object and date, including exact
duplicates; adjacent bookings are allowed. Ranges must use `HH:MM-HH:MM` within
one day. Booking validation rechecks the local reservation file even when search
results are stale. Invalid saved JSON raises an error instead of being overwritten.
Search results still come from static availability, so an option can be rejected
when the user presses Reserve.

This is a single-process demo. The in-process lock protects concurrent Streamlit
sessions, but separate app processes must not share the JSON file. There is no
cross-process locking, authentication, capacity model, cancellation workflow, or
production booking guarantee. Each object is treated as exclusively booked for a
slot. Do not use it to manage real reservations.
