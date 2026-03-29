#!/bin/bash

# Script to organize credential files into the credentials directory
# This script safely moves OAuth credential files to the new centralized location

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDS_DIR="$SCRIPT_DIR/credentials"

echo "========================================="
echo "  Credential File Organization Script"
echo "========================================="
echo ""

# Create credentials directory if it doesn't exist
if [ ! -d "$CREDS_DIR" ]; then
    echo "Creating credentials directory..."
    mkdir -p "$CREDS_DIR"
fi

# Function to move or copy file
move_credential_file() {
    local old_name=$1
    local new_name=$2
    
    if [ -f "$SCRIPT_DIR/$old_name" ]; then
        if [ -f "$CREDS_DIR/$new_name" ]; then
            echo "⚠️  $new_name already exists in credentials/"
            echo "   Keeping existing file. Old file at root: $old_name"
        else
            echo "📦 Moving $old_name → credentials/$new_name"
            cp "$SCRIPT_DIR/$old_name" "$CREDS_DIR/$new_name"
            echo "✅ Copied successfully (original kept for safety)"
        fi
    else
        echo "ℹ️  $old_name not found (skipping)"
    fi
}

echo "Organizing credential files..."
echo ""

# Move Gmail credentials
move_credential_file "gmail.json" "gmail.json"

# Move Google Sheets credentials (could be sheet.json or gsheet.json)
if [ -f "$SCRIPT_DIR/sheet.json" ]; then
    move_credential_file "sheet.json" "google_sheets.json"
elif [ -f "$SCRIPT_DIR/gsheet.json" ]; then
    move_credential_file "gsheet.json" "google_sheets.json"
fi

# Move Google Forms credentials
move_credential_file "google_form.json" "google_forms.json"

# Move Google Docs credentials (could be gdoc.json or use gsheet.json)
if [ -f "$SCRIPT_DIR/gdoc.json" ]; then
    move_credential_file "gdoc.json" "google_docs.json"
elif [ ! -f "$CREDS_DIR/google_docs.json" ] && [ -f "$SCRIPT_DIR/gsheet.json" ]; then
    echo "📦 Using gsheet.json as google_docs.json"
    cp "$SCRIPT_DIR/gsheet.json" "$CREDS_DIR/google_docs.json"
    echo "✅ Copied successfully"
fi

# Move YouTube credentials
move_credential_file "youtube.json" "youtube.json"

echo ""
echo "========================================="
echo "  Summary"
echo "========================================="
echo ""

# List files in credentials directory
if [ -d "$CREDS_DIR" ]; then
    echo "Files in credentials/ directory:"
    ls -lh "$CREDS_DIR"/*.json 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    echo ""
fi

echo "✅ Organization complete!"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - Original files kept in root directory for safety"
echo "   - Test OAuth flows before deleting old files"
echo "   - Update Google Cloud Console redirect URIs if needed"
echo "   - Verify .gitignore excludes credentials/*.json"
echo ""
echo "Next steps:"
echo "   1. Test each OAuth flow (Gmail, Sheets, Forms, Docs, YouTube)"
echo "   2. Once confirmed working, delete old credential files from root"
echo "   3. Update your deployment scripts if needed"
echo ""
