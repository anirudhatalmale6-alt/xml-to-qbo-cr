# XML to QBO — Costa Rica Invoice Automation

Automatically processes Costa Rica electronic invoice XML files (Factura Electrónica v4.3/v4.4) and creates Bills in QuickBooks Online.

## Features

- **XML Parser**: Parses Costa Rica Factura Electrónica XML (Ministerio de Hacienda format)
- **Email Monitoring**: Automatically detects XML attachments from incoming emails (IMAP)
- **QBO Integration**: Creates Vendors and Bills via QuickBooks Online API (OAuth 2.0)
- **Duplicate Detection**: Prevents re-processing of already imported invoices
- **Web Dashboard**: Monitor processing status, view logs, and manually upload XML files
- **Validation**: Validates XML structure and totals before sending to QBO

## Architecture

```
Email Inbox → Email Monitor → XML Parser → Validator → QBO API
                                                          ↓
                              Dashboard ← Database ← Bill Created
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Set Up QuickBooks Online API

1. Go to https://developer.intuit.com and create a free account
2. Create a new app → "QuickBooks Online and Payments"
3. Copy the **Client ID** and **Client Secret** to your `.env` file
4. Set `QBO_REDIRECT_URI=http://localhost:5000/qbo/callback` in the Intuit developer portal

### 4. Set Up Email (Gmail Example)

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password: Google Account → Security → App Passwords
3. Set `EMAIL_USER` and `EMAIL_PASSWORD` (app password) in `.env`

### 5. Run the Application

```bash
python main.py
```

The dashboard will be available at `http://localhost:5000`

### 6. Connect to QuickBooks

1. Open `http://localhost:5000` in your browser
2. Click "Connect QBO" in the top-right corner
3. Authorize with your QuickBooks Online account
4. The system is now ready to process invoices!

## Manual XML Upload

You can also upload XML files manually through the dashboard:
1. Go to `http://localhost:5000/upload`
2. Select one or more XML files
3. Click "Process XML Files"

## API Endpoint

```bash
# Upload and process a single XML file
curl -X POST http://localhost:5000/api/process \
  -F "xml_file=@invoice.xml"
```

## Project Structure

```
xml-to-qbo/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── config/
│   └── settings.py           # Configuration management
├── src/
│   ├── processor.py          # Main processing pipeline
│   ├── database.py           # SQLite database layer
│   ├── parsers/
│   │   └── cr_invoice_parser.py  # Costa Rica XML parser
│   ├── qbo/
│   │   ├── auth.py           # OAuth 2.0 handler
│   │   ├── client.py         # QBO API client
│   │   ├── bill_builder.py   # Invoice → Bill converter
│   │   └── tax_setup.py      # Tax code discovery
│   ├── email/
│   │   └── monitor.py        # IMAP email monitor
│   └── dashboard/
│       ├── app.py            # Flask web dashboard
│       └── templates/        # HTML templates
└── tests/
    ├── test_parser.py        # Parser tests
    └── sample_xml/           # Sample XML files
```

## Supported XML Format

Costa Rica Factura Electrónica v4.3 and v4.4 from the Ministerio de Hacienda, including:
- Invoice header (Clave, NumeroConsecutivo, FechaEmision)
- Emisor (issuer/vendor) information
- Receptor (receiver) information
- Line items with CABYS codes, discounts, and IVA taxes
- Other charges (e.g., service charge)
- Summary with totals and currency

## Email Providers

Tested with:
- **Gmail** (IMAP with App Password)
- **Outlook/Microsoft 365** (IMAP)
- Any standard IMAP provider

## License

Private project — all rights reserved.
