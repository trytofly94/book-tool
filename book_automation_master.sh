#!/bin/bash

# ==============================================
# Master Book Automation Script
# Downloads books and prepares them for Goodreads
# ==============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CALIBRE_INGEST_DIR="/Volumes/Entertainment/Bücher/Calibre-Ingest"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}          Book Automation Master Script        ${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_step() {
    echo -e "\n${YELLOW}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    print_step "Überprüfe Abhängigkeiten..."

    local deps=("librarian" "calibre" "ebook-convert" "ebook-meta" "python3")
    local missing=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done

    if [ ${#missing[@]} -eq 0 ]; then
        print_success "Alle Abhängigkeiten gefunden"
        return 0
    else
        print_error "Fehlende Abhängigkeiten: ${missing[*]}"
        echo "Installiere fehlende Tools:"
        echo "  - librarian: Siehe deine bisherige Installation"
        echo "  - calibre: brew install --cask calibre"
        echo "  - python3: brew install python3"
        return 1
    fi
}

download_books() {
    print_step "Starte Book Download..."

    echo "Verfügbare Serien:"
    echo "1. Brandon Sanderson - Sturmlicht Chroniken"
    echo "2. Eigene Eingabe"

    read -p "Wählen Sie (1-2): " choice

    case $choice in
        1)
            author="Brandon Sanderson"
            series="Sturmlicht"
            format="mobi"
            ;;
        2)
            read -p "Autor: " author
            read -p "Serie/Titel: " series
            read -p "Format (mobi/epub) [mobi]: " format
            format=${format:-mobi}
            ;;
        *)
            print_error "Ungültige Auswahl"
            return 1
            ;;
    esac

    print_step "Lade herunter: $author - $series ($format)"

    if python3 "$SCRIPT_DIR/auto_download_books.py" "$author" "$series" "$format"; then
        print_success "Download abgeschlossen"
        return 0
    else
        print_error "Download fehlgeschlagen"
        return 1
    fi
}

prepare_for_goodreads() {
    print_step "Bereite Bücher für Goodreads vor..."

    echo "HINWEIS: Für die Goodreads-Integration benötigen Sie Amazon ASINs."
    echo "Diese finden Sie auf den Amazon Kindle Store Seiten der Bücher."
    echo ""
    read -p "Möchten Sie fortfahren? (j/n): " proceed

    if [[ $proceed =~ ^[Jj]$ ]]; then
        if python3 "$SCRIPT_DIR/calibre_goodreads_prep.py"; then
            print_success "Goodreads-Vorbereitung abgeschlossen"
            return 0
        else
            print_error "Goodreads-Vorbereitung fehlgeschlagen"
            return 1
        fi
    else
        echo "Überspringe Goodreads-Vorbereitung"
        return 0
    fi
}

show_summary() {
    print_step "Zusammenfassung"

    echo "Dateien in $CALIBRE_INGEST_DIR:"
    ls -lh "$CALIBRE_INGEST_DIR"/*.{mobi,epub,azw3} 2>/dev/null || echo "Keine eBook-Dateien gefunden"

    echo ""
    echo "Nächste Schritte:"
    echo "1. Importiere Bücher in Calibre"
    echo "2. Für Goodreads: Übertrage *_goodreads.azw3 Dateien per USB zum Kindle"
    echo "3. Teste die Goodreads-Integration auf deinem Kindle"
}

main() {
    print_header

    # Überprüfe Abhängigkeiten
    if ! check_dependencies; then
        exit 1
    fi

    # Erstelle Verzeichnis falls nötig
    mkdir -p "$CALIBRE_INGEST_DIR"

    while true; do
        echo ""
        echo "Was möchten Sie tun?"
        echo "1. Bücher herunterladen"
        echo "2. Für Goodreads vorbereiten"
        echo "3. Zusammenfassung anzeigen"
        echo "4. Beenden"

        read -p "Wählen Sie (1-4): " action

        case $action in
            1)
                download_books
                ;;
            2)
                prepare_for_goodreads
                ;;
            3)
                show_summary
                ;;
            4)
                echo "Auf Wiedersehen!"
                exit 0
                ;;
            *)
                print_error "Ungültige Auswahl"
                ;;
        esac
    done
}

main "$@"
