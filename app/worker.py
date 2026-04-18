from __future__ import annotations

import time


def main() -> None:
    print("FacilERP worker iniciado. No hay tareas asíncronas configuradas todavía.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
