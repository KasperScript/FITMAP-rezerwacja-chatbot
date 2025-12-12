import json
from db_loader import load_availability
from agent import handle_user_query 
from parsing import extract_json_candidate

def pretty_print_options(payload):
    options = payload.get("options", [])
    if not options:
        print("Brak dopasowań w JSON (options jest puste).")
        return

    print("\nNajlepiej dopasowane opcje:")
    for opt in options[:5]:
        activities = opt.get("activities") or []
        activities = [str(a) for a in activities if a is not None]
        activities_str = ", ".join(activities) if activities else "brak danych"
        obj_type = opt.get("object_type") or "brak typu"
        city = opt.get("city")
        name = opt.get("object_name") or "brak nazwy"
        obj_id = opt.get("object_id", "brak id")
        header = f"- ID: {obj_id} | {name} ({obj_type})"
        if isinstance(city, str) and city.strip():
            header = f"- ID: {obj_id} | {name} ({obj_type}, {city})"
        date = opt.get("date")
        time_range = opt.get("time_range") or "brak godzin"
        time_line = f"  Godziny: {time_range}" if not date else f"  Data: {date}  Godziny: {time_range}"
        print(
            f"{header}\n"
            f"  Zajęcia: {activities_str}\n"
            f"{time_line}\n"
            f"  Cena: {opt.get('price_per_hour') if opt.get('price_per_hour') is not None else 'brak ceny'} zł/h\n"
        )

def main():
    db_json = load_availability()
    last_filters = None

    print("Agent do wyszukiwania obiektów sportowych.")
    print('Zadaj pytanie, np. "Szukam jogi w środę po 18 do 100 zł".')
    print('Wpisz "exit" aby zakończyć.\n')

    while True:
        user_query = input("Ty: ").strip()
        if not user_query:
            continue
        if user_query.lower() in {"exit", "quit", "koniec"}:
            break

        result = handle_user_query(user_query, db_json, last_filters)

        raw_answer = result["raw_answer"]
        payload = result["parsed_payload"]
        last_filters = result.get("filters")

        print("\n=== RAW MODEL ANSWER START ===\n")
        print(raw_answer)
        print("\n=== RAW MODEL ANSWER END ===\n")

        candidate = extract_json_candidate(raw_answer)
        if candidate:
            print("[Debug] JSON candidate detected:\n")
            print(candidate)
        else:
            print("[Debug] No JSON candidate detected.\n")

        if payload:
            print("\n[Parsowany JSON]:")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            pretty_print_options(payload)
        else:
            print("\n[Uwaga] Nie udało się zparsować bloku JSON z odpowiedzi.")

        print("\n" + "-" * 60 + "\n")

if __name__ == "__main__":
    main()
