#!/usr/bin/env python3
"""
Erweiterte Calibre-Kontrolle mit verschiedenen Methoden
"""

import subprocess
import os


class CalibreController:
    """
    Umfassende Calibre-Steuerung über CLI-Tools
    """

    def __init__(self, library_path=None):
        self.library_path = library_path
        self.tools_available = self.check_calibre_installation()

    def check_calibre_installation(self):
        """Überprüft ob Calibre installiert ist"""
        tools = ["calibredb", "ebook-convert", "ebook-meta"]
        available = {}

        for tool in tools:
            try:
                result = subprocess.run(
                    [tool, "--version"], capture_output=True, text=True
                )
                available[tool] = result.returncode == 0
            except FileNotFoundError:
                available[tool] = False

        return available

    def get_base_cmd(self, tool):
        """Erstellt Basis-Kommando mit optionalem Library-Pfad"""
        cmd = [tool]
        if self.library_path and tool == "calibredb":
            cmd.extend(["--library-path", self.library_path])
        return cmd

    # === BIBLIOTHEKS-VERWALTUNG ===

    def add_books_from_directory(self, directory, options=None):
        """
        Fügt alle eBooks aus einem Verzeichnis zur Bibliothek hinzu
        """
        if not self.tools_available.get("calibredb", False):
            raise RuntimeError("calibredb nicht verfügbar")

        cmd = self.get_base_cmd("calibredb") + ["add", "--recurse", directory]

        if options:
            for key, value in options.items():
                cmd.extend([f"--{key}", str(value)])

        print(f"Führe aus: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def list_books(self, search=None, limit=None):
        """Listet Bücher mit optionaler Suche"""
        if not self.tools_available.get("calibredb", False):
            return []

        cmd = self.get_base_cmd("calibredb") + ["list"]

        if search:
            cmd.extend(["-s", search])
        if limit:
            cmd.extend(["--limit", str(limit)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            # Parse die Ausgabe (vereinfacht)
            lines = result.stdout.strip().split("\n")
            books = []
            for line in lines[1:]:  # Erste Zeile ist Header
                if line.strip():
                    parts = line.split("\t") if "\t" in line else line.split()
                    if len(parts) >= 2:
                        books.append(
                            {
                                "id": parts[0],
                                "title": parts[1] if len(parts) > 1 else "Unknown",
                                "author": parts[2] if len(parts) > 2 else "Unknown",
                            }
                        )
            return books

        return []

    def get_book_metadata(self, book_id):
        """Holt detaillierte Metadaten für ein Buch"""
        cmd = self.get_base_cmd("calibredb") + ["show_metadata", str(book_id)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            # Parse Metadaten (vereinfacht)
            metadata = {}
            for line in result.stdout.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip().lower()] = value.strip()
            return metadata

        return None

    # === FORMAT-KONVERTIERUNG ===

    def convert_book(self, input_path, output_path, conversion_options=None):
        """
        Konvertiert ein Buch zwischen verschiedenen Formaten
        """
        if not self.tools_available.get("ebook-convert", False):
            raise RuntimeError("ebook-convert nicht verfügbar")

        cmd = ["ebook-convert", input_path, output_path]

        # Standard-Optionen für bessere Qualität
        default_options = {
            "margin-left": "5",
            "margin-right": "5",
            "margin-top": "5",
            "margin-bottom": "5",
            "change-justification": "left",
        }

        # Spezielle Optionen für KFX/Kindle
        if output_path.endswith((".azw3", ".kfx")):
            default_options.update(
                {"output-profile": "kindle_fire", "no-inline-toc": None}
            )

        # Kombiniere mit benutzerdefinierten Optionen
        if conversion_options:
            default_options.update(conversion_options)

        # Füge Optionen zum Kommando hinzu
        for key, value in default_options.items():
            if value is None:
                cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])

        print(
            f"Konvertiere: {os.path.basename(input_path)} → {os.path.basename(output_path)}"
        )
        result = subprocess.run(cmd, capture_output=True, text=True)

        return {
            "success": result.returncode == 0,
            "output_file": output_path if result.returncode == 0 else None,
            "stderr": result.stderr,
        }

    def batch_convert(
        self, input_dir, output_dir, input_format, output_format, options=None
    ):
        """Konvertiert alle Bücher eines Formats in einem Verzeichnis"""
        results = []

        # Erstelle Output-Verzeichnis
        os.makedirs(output_dir, exist_ok=True)

        # Finde alle Dateien mit dem Input-Format
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(f".{input_format.lower()}"):
                input_path = os.path.join(input_dir, filename)
                output_filename = os.path.splitext(filename)[0] + f".{output_format}"
                output_path = os.path.join(output_dir, output_filename)

                result = self.convert_book(input_path, output_path, options)
                results.append(
                    {
                        "input": filename,
                        "output": output_filename,
                        "success": result["success"],
                    }
                )

        return results

    # === METADATEN-VERWALTUNG ===

    def set_book_metadata(self, book_path, metadata):
        """
        Setzt Metadaten für eine eBook-Datei
        """
        if not self.tools_available.get("ebook-meta", False):
            raise RuntimeError("ebook-meta nicht verfügbar")

        cmd = ["ebook-meta", book_path]

        # Füge Metadaten-Felder hinzu
        for field, value in metadata.items():
            if field == "identifier":
                # Spezialbehandlung für Identifier (z.B. Amazon ASIN)
                cmd.extend(["--identifier", value])
            elif field == "cover":
                cmd.extend(["--cover", value])
            else:
                cmd.extend([f"--{field}", str(value)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def get_book_metadata_from_file(self, book_path):
        """Liest Metadaten aus einer eBook-Datei"""
        cmd = ["ebook-meta", book_path]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            # Parse die Metadaten
            metadata = {}
            for line in result.stdout.split("\n"):
                if ":" in line and not line.startswith(" "):
                    key, value = line.split(":", 1)
                    metadata[key.strip().lower()] = value.strip()
            return metadata

        return None

    # === BATCH-OPERATIONEN ===

    def prepare_books_for_goodreads(self, directory):
        """
        Bereitet alle Bücher in einem Verzeichnis für Goodreads vor
        """
        results = []
        supported_formats = [".mobi", ".epub", ".azw3"]

        for filename in os.listdir(directory):
            if any(filename.lower().endswith(ext) for ext in supported_formats):
                file_path = os.path.join(directory, filename)

                print(f"\n--- Verarbeite: {filename} ---")

                # 1. Aktuelle Metadaten anzeigen
                current_metadata = self.get_book_metadata_from_file(file_path)
                if current_metadata:
                    print(f"Titel: {current_metadata.get('title', 'Unbekannt')}")
                    print(f"Autor: {current_metadata.get('author(s)', 'Unbekannt')}")

                # 2. ASIN abfragen
                asin = input("Amazon ASIN eingeben (beginnt mit 'B'): ").strip()

                if asin and asin.startswith("B") and len(asin) == 10:
                    # 3. ASIN zu Metadaten hinzufügen
                    if self.set_book_metadata(
                        file_path, {"identifier": f"amazon:{asin}"}
                    ):
                        print(f"✓ ASIN {asin} hinzugefügt")

                        # 4. Zu KFX für Goodreads konvertieren
                        kfx_filename = os.path.splitext(filename)[0] + "_goodreads.azw3"
                        kfx_path = os.path.join(directory, kfx_filename)

                        convert_result = self.convert_book(file_path, kfx_path)

                        if convert_result["success"]:
                            results.append(
                                {
                                    "original": filename,
                                    "goodreads_version": kfx_filename,
                                    "asin": asin,
                                    "status": "success",
                                }
                            )
                            print(f"✓ KFX-Version erstellt: {kfx_filename}")
                        else:
                            print(
                                f"✗ Konvertierung fehlgeschlagen: {convert_result['stderr']}"
                            )
                    else:
                        print("✗ Fehler beim Hinzufügen der ASIN")
                else:
                    print("⚠ Ungültige ASIN, überspringe...")

        return results


def main():
    print("=== Erweiterte Calibre-Kontrolle ===\n")

    # Initialisiere Controller
    controller = CalibreController()

    # Zeige verfügbare Tools
    print("Verfügbare Calibre-Tools:")
    for tool, available in controller.tools_available.items():
        status = "✓" if available else "✗"
        print(f"  {status} {tool}")

    if not any(controller.tools_available.values()):
        print("\n⚠ Kein Calibre-Tool verfügbar!")
        print("Installation: brew install --cask calibre")
        return

    # Beispiel-Verzeichnis
    test_dir = "/Volumes/Entertainment/Bücher/Calibre-Ingest"

    if os.path.exists(test_dir):
        print(f"\nVerzeichnis gefunden: {test_dir}")

        # Zeige verfügbare Operationen
        print("\nVerfügbare Operationen:")
        print("1. Bücher zur Bibliothek hinzufügen")
        print("2. Formate konvertieren")
        print("3. Für Goodreads vorbereiten")
        print("4. Metadaten anzeigen")

        choice = input("\nAuswahl (1-4): ").strip()

        if choice == "1":
            # Bücher zur Bibliothek hinzufügen
            result = controller.add_books_from_directory(
                test_dir, {"duplicates": "ignore", "add-empty": False}
            )
            print(f"Ergebnis: {result}")

        elif choice == "2":
            # Batch-Konvertierung
            results = controller.batch_convert(
                test_dir, test_dir, "mobi", "epub", {"output-profile": "generic_eink"}
            )
            print(f"Konvertiert: {len([r for r in results if r['success']])} Bücher")

        elif choice == "3":
            # Goodreads-Vorbereitung
            results = controller.prepare_books_for_goodreads(test_dir)
            print(f"\nGoodreads-Ready: {len(results)} Bücher")

        elif choice == "4":
            # Metadaten anzeigen
            for filename in os.listdir(test_dir):
                if filename.endswith((".mobi", ".epub")):
                    file_path = os.path.join(test_dir, filename)
                    metadata = controller.get_book_metadata_from_file(file_path)
                    if metadata:
                        print(f"\n{filename}:")
                        for key, value in list(metadata.items())[:5]:
                            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
