#!/usr/bin/env python3
"""
Parallel KFX Conversion mit KFX Plugin Support
Implementiert die Recherche-Erkenntnisse für parallele Batch-Konvertierung
"""

import subprocess
import os
import concurrent.futures
from pathlib import Path
from threading import Lock


class ParallelKFXConverter:
    """
    Parallele KFX-Konvertierung mit Plugin-Unterstützung
    Basierend auf der Recherche zu Calibre-Automatisierung
    """

    def __init__(self, library_path=None, max_workers=4):
        self.library_path = library_path
        self.max_workers = max_workers
        self.conversion_lock = Lock()
        self.results = []

        # Prüfe Systemvoraussetzungen
        self.check_system_requirements()

    def check_system_requirements(self):
        """Prüft ob alle erforderlichen Tools verfügbar sind"""
        print("=== System-Voraussetzungen prüfen ===")

        # Calibre CLI Tools
        calibre_tools = ["calibre", "ebook-convert"]
        for tool in calibre_tools:
            if not self.check_tool_availability(tool):
                print(f"✗ {tool} nicht verfügbar")
                return False
            else:
                print(f"✓ {tool} verfügbar")

        # KFX Output Plugin prüfen
        if self.check_kfx_plugin():
            print("✓ KFX Output Plugin verfügbar")
        else:
            print("⚠ KFX Output Plugin nicht gefunden")
            print("  Installation: calibre-customize -a KFXOutput.zip")

        # Kindle Previewer 3 prüfen
        if self.check_kindle_previewer():
            print("✓ Kindle Previewer 3 verfügbar")
        else:
            print("⚠ Kindle Previewer 3 nicht gefunden")
            print("  Download: https://kdp.amazon.com/en_US/help/topic/G202131170")

        return True

    def check_tool_availability(self, tool):
        """Prüft ob ein CLI-Tool verfügbar ist"""
        try:
            result = subprocess.run(
                [tool, "--version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def check_kfx_plugin(self):
        """Prüft ob KFX Output Plugin installiert ist"""
        try:
            # Prüfe über calibre-customize
            result = subprocess.run(
                ["calibre-customize", "-l"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                return "KFX Output" in result.stdout or "KFXOutput" in result.stdout
        except subprocess.SubprocessError:
            pass

        # Alternative: Prüfe Calibre Plugin-Verzeichnis
        plugin_dirs = [
            os.path.expanduser("~/Library/Preferences/calibre/plugins"),  # macOS
            os.path.expanduser("~/.config/calibre/plugins"),  # Linux
            os.path.expanduser("~/AppData/Roaming/calibre/plugins"),  # Windows
        ]

        for plugin_dir in plugin_dirs:
            if os.path.exists(plugin_dir):
                for file in os.listdir(plugin_dir):
                    if "kfx" in file.lower():
                        return True

        return False

    def check_kindle_previewer(self):
        """Prüft ob Kindle Previewer 3 installiert ist"""
        previewer_paths = [
            "/Applications/Kindle Previewer 3.app",  # macOS
            "/usr/local/bin/kindle-previewer",  # Linux
            "C:\\Program Files (x86)\\Amazon\\Kindle Previewer 3\\Kindle Previewer.exe",  # Windows
        ]

        return any(os.path.exists(path) for path in previewer_paths)

    def get_base_cmd(self):
        """Erstellt Basis-Kommando mit Library-Pfad"""
        cmd = ["calibredb"]
        if self.library_path:
            cmd.extend(["--library-path", self.library_path])
        return cmd

    def find_conversion_candidates(self, input_dir, input_formats=None):
        """
        Findet alle Dateien die für KFX-Konvertierung geeignet sind
        """
        if not input_formats:
            input_formats = [".epub", ".mobi", ".azw", ".azw3", ".pdf"]

        candidates = []

        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if any(file.lower().endswith(fmt) for fmt in input_formats):
                    full_path = os.path.join(root, file)

                    # Überspringe bereits konvertierte KFX-Dateien
                    if "_kfx" not in file.lower():
                        candidates.append(
                            {
                                "input_path": full_path,
                                "filename": file,
                                "format": Path(file).suffix.lower(),
                            }
                        )

        return candidates

    def convert_single_to_kfx(self, input_path, output_path, conversion_options=None):
        """
        Konvertiert eine einzelne Datei zu KFX
        """
        try:
            # Basis-Kommando für Konvertierung
            cmd = ["ebook-convert", input_path, output_path]

            # KFX-spezifische Optionen (aus der Recherche)
            kfx_options = {
                "output-profile": "kindle_fire",
                "no-inline-toc": True,
                "margin-left": "5",
                "margin-right": "5",
                "margin-top": "5",
                "margin-bottom": "5",
                "change-justification": "left",
                "remove-paragraph-spacing": True,
                "remove-paragraph-spacing-indent-size": "1.5",
                "insert-blank-line": True,
                "insert-blank-line-size": "0.5",
            }

            # Erweiterte KFX-Optionen wenn Plugin verfügbar
            if self.check_kfx_plugin():
                kfx_options.update(
                    {
                        "enable-heuristics": True,
                        "markup-chapter-headings": True,
                        "remove-fake-margins": True,
                    }
                )

            # Benutzerdefinierte Optionen überschreiben Standard-Optionen
            if conversion_options:
                kfx_options.update(conversion_options)

            # Optionen zum Kommando hinzufügen
            for key, value in kfx_options.items():
                if isinstance(value, bool):
                    if value:
                        cmd.append(f"--{key}")
                else:
                    cmd.extend([f"--{key}", str(value)])

            # Konvertierung ausführen
            with self.conversion_lock:
                print(f"Konvertiere: {os.path.basename(input_path)} → KFX")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            success = result.returncode == 0

            with self.conversion_lock:
                if success:
                    print(f"✓ Erfolgreich: {os.path.basename(output_path)}")
                else:
                    print(f"✗ Fehlgeschlagen: {os.path.basename(input_path)}")
                    print(f"  Fehler: {result.stderr[:200]}...")

            return {
                "input_path": input_path,
                "output_path": output_path,
                "success": success,
                "error": result.stderr if not success else None,
                "file_size": (
                    os.path.getsize(output_path)
                    if success and os.path.exists(output_path)
                    else 0
                ),
            }

        except subprocess.TimeoutExpired:
            return {
                "input_path": input_path,
                "output_path": output_path,
                "success": False,
                "error": "Conversion timeout (300s exceeded)",
                "file_size": 0,
            }
        except Exception as e:
            return {
                "input_path": input_path,
                "output_path": output_path,
                "success": False,
                "error": str(e),
                "file_size": 0,
            }

    def parallel_batch_convert(
        self, input_dir, output_dir=None, input_formats=None, dry_run=False
    ):
        """
        Parallele Batch-Konvertierung zu KFX
        Implementiert die Recherche-Erkenntnisse für parallele Verarbeitung
        """
        if not output_dir:
            output_dir = os.path.join(input_dir, "kfx_output")

        os.makedirs(output_dir, exist_ok=True)

        # Finde Konvertierungs-Kandidaten
        candidates = self.find_conversion_candidates(input_dir, input_formats)

        if not candidates:
            print("Keine Dateien für KFX-Konvertierung gefunden")
            return []

        print(f"Gefunden: {len(candidates)} Dateien für KFX-Konvertierung")
        print(f"Parallele Worker: {self.max_workers}")

        if dry_run:
            print("\n=== DRY RUN - Keine Konvertierung ===")
            for candidate in candidates:
                output_filename = Path(candidate["filename"]).stem + "_kfx.azw3"
                print(
                    f"Würde konvertieren: {candidate['filename']} → {output_filename}"
                )
            return []

        # Erstelle Konvertierungs-Jobs
        conversion_jobs = []
        for candidate in candidates:
            output_filename = Path(candidate["filename"]).stem + "_kfx.azw3"
            output_path = os.path.join(output_dir, output_filename)

            # Überspringe bereits existierende Dateien
            if not os.path.exists(output_path):
                conversion_jobs.append(
                    {
                        "input_path": candidate["input_path"],
                        "output_path": output_path,
                        "filename": candidate["filename"],
                    }
                )

        if not conversion_jobs:
            print("Alle Dateien bereits konvertiert")
            return []

        print(f"Starte parallele Konvertierung von {len(conversion_jobs)} Dateien...")

        # Parallele Verarbeitung mit ThreadPoolExecutor
        results = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # Submit alle Jobs
            future_to_job = {
                executor.submit(
                    self.convert_single_to_kfx, job["input_path"], job["output_path"]
                ): job
                for job in conversion_jobs
            }

            # Sammle Ergebnisse
            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    print(f'✗ Job für {job["filename"]} generierte Ausnahme: {exc}')
                    results.append(
                        {
                            "input_path": job["input_path"],
                            "output_path": job["output_path"],
                            "success": False,
                            "error": str(exc),
                            "file_size": 0,
                        }
                    )

        # Zusammenfassung
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        print("\n=== Konvertierungs-Zusammenfassung ===")
        print(f"Erfolgreich: {len(successful)}")
        print(f"Fehlgeschlagen: {len(failed)}")
        print(
            f"Gesamt-Ausgabe-Größe: {sum(r['file_size'] for r in successful) / 1024 / 1024:.1f} MB"
        )

        if failed:
            print("\nFehlgeschlagene Konvertierungen:")
            for fail in failed:
                print(
                    f"  ✗ {os.path.basename(fail['input_path'])}: {fail['error'][:100]}..."
                )

        return results

    def convert_library_to_kfx(self, book_filter=None, limit=None, dry_run=False):
        """
        Konvertiert Bücher aus der Calibre-Bibliothek zu KFX
        """
        if not self.library_path:
            print("✗ Kein Library-Pfad angegeben")
            return []

        try:
            # Liste Bücher aus der Bibliothek
            cmd = self.get_base_cmd() + [
                "list",
                "--fields",
                "id,title,authors,formats,path",
            ]

            if book_filter:
                cmd.extend(["-s", book_filter])
            if limit:
                cmd.extend(["--limit", str(limit)])

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"✗ Fehler beim Auflisten der Bücher: {result.stderr}")
                return []

            # Parse Bücher
            books = []
            lines = result.stdout.strip().split("\n")[1:]  # Skip header

            for line in lines:
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        book_id, title, authors, formats, path = (
                            parts[0],
                            parts[1],
                            parts[2],
                            parts[3],
                            parts[4],
                        )

                        # Prüfe ob bereits KFX vorhanden
                        if (
                            "AZW3" not in formats.upper()
                            or "kfx" not in formats.lower()
                        ):
                            book_path = os.path.join(self.library_path, path)
                            if os.path.exists(book_path):
                                books.append(
                                    {
                                        "id": book_id,
                                        "title": title,
                                        "authors": authors,
                                        "formats": formats,
                                        "path": book_path,
                                    }
                                )

            if not books:
                print("Keine Bücher für KFX-Konvertierung gefunden")
                return []

            print(f"Gefunden: {len(books)} Bücher für KFX-Konvertierung")

            if dry_run:
                print("\n=== DRY RUN - Library Konvertierung ===")
                for book in books:
                    print(f"Würde konvertieren: {book['title']} von {book['authors']}")
                return []

            # Konvertiere jeden Buch-Ordner
            all_results = []
            for book in books:
                print(f"\n--- Konvertiere Bibliotheksbuch: {book['title']} ---")
                results = self.parallel_batch_convert(book["path"], dry_run=False)
                all_results.extend(results)

            return all_results

        except Exception as e:
            print(f"✗ Fehler bei Library-Konvertierung: {e}")
            return []

    def install_kfx_plugin(self):
        """
        Hilft bei der Installation des KFX Output Plugins
        """
        print("=== KFX Output Plugin Installation ===")
        print("1. Lade das KFX Output Plugin herunter:")
        print("   https://www.mobileread.com/forums/showthread.php?t=272407")
        print()
        print("2. Installiere das Plugin:")
        print("   calibre-customize -a KFXOutput.zip")
        print()
        print("3. Oder über die GUI:")
        print("   Calibre → Preferences → Plugins → Load plugin from file")
        print()
        print("4. Starte Calibre neu nach der Installation")
        print()

        install_now = input("Plugin jetzt installieren? (j/n): ").strip().lower()
        if install_now == "j":
            plugin_path = input("Pfad zur KFXOutput.zip Datei: ").strip()
            if os.path.exists(plugin_path):
                try:
                    result = subprocess.run(
                        ["calibre-customize", "-a", plugin_path],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        print("✓ Plugin erfolgreich installiert")
                        print("Bitte starte Calibre neu")
                        return True
                    else:
                        print(f"✗ Installation fehlgeschlagen: {result.stderr}")
                except Exception as e:
                    print(f"✗ Fehler bei der Installation: {e}")
            else:
                print("✗ Plugin-Datei nicht gefunden")

        return False


def main():
    """Hauptfunktion für parallele KFX-Konvertierung"""
    print("=== Parallel KFX Converter ===")

    # Standardpfade
    input_dir = "/Volumes/Entertainment/Bücher/Calibre-Ingest"
    library_path = os.path.expanduser("~/Calibre Library")

    # Bestimme Pfade
    if not os.path.exists(input_dir):
        input_dir = input("Input-Verzeichnis: ").strip()

    if not os.path.exists(library_path):
        library_path = None

    # Initialisiere Converter
    converter = ParallelKFXConverter(library_path=library_path, max_workers=4)

    # Menü
    while True:
        print("\n=== Optionen ===")
        print("1. System-Voraussetzungen prüfen")
        print("2. KFX Plugin installieren")
        print("3. Verzeichnis zu KFX konvertieren (Dry Run)")
        print("4. Verzeichnis zu KFX konvertieren (Live)")
        print("5. Calibre-Bibliothek zu KFX konvertieren (Dry Run)")
        print("6. Calibre-Bibliothek zu KFX konvertieren (Live)")
        print("7. Beenden")

        choice = input("Auswahl (1-7): ").strip()

        if choice == "1":
            converter.check_system_requirements()

        elif choice == "2":
            converter.install_kfx_plugin()

        elif choice == "3":
            results = converter.parallel_batch_convert(input_dir, dry_run=True)

        elif choice == "4":
            max_workers = input("Anzahl parallele Worker (default: 4): ").strip()
            if max_workers:
                converter.max_workers = int(max_workers)

            converter.parallel_batch_convert(input_dir, dry_run=False)

        elif choice == "5":
            if converter.library_path:
                limit = input("Limit (leer für alle): ").strip()
                limit = int(limit) if limit else None
                converter.convert_library_to_kfx(limit=limit, dry_run=True)
            else:
                print("Kein Calibre Library Pfad verfügbar")

        elif choice == "6":
            if converter.library_path:
                limit = input("Limit (leer für alle): ").strip()
                limit = int(limit) if limit else None
                max_workers = input("Anzahl parallele Worker (default: 4): ").strip()
                if max_workers:
                    converter.max_workers = int(max_workers)

                converter.convert_library_to_kfx(limit=limit, dry_run=False)
            else:
                print("Kein Calibre Library Pfad verfügbar")

        elif choice == "7":
            break

        else:
            print("Ungültige Auswahl")


if __name__ == "__main__":
    main()
