# Outlook AutoReport – IT Approval Checklist

## STOP – Confirm Before Deployment
1. **Kutools Availability**: Confirm Kutools for Outlook (latest build) is licensed and can be
   installed on the target workstation.
2. **pywin32 Allowance**: Verify that Python 3.10+ and the `pywin32` package are allowed under IT
   security policy.
3. **Classic Outlook Mode**: Ensure users run *Classic* Outlook 2021. If New Outlook is enforced,
   request a policy exception or follow the fallback export plan (manual CSV export via Outlook on
   the web).
4. **Tesseract OCR Installation**: Confirm permission to install Tesseract OCR (Windows installer or
   winget package). Document the installation path for configuration.
5. **ABBYY Cloud Access (Optional)**: If ABBYY OCR will be integrated, obtain API credentials through
   the vendor onboarding process and store them in the enterprise secrets vault.

## IT Approvals Required
- **Software Installation**: Python runtime, Tesseract OCR, Kutools add-in.
- **Scheduled Task**: Approval to create a Windows Task Scheduler job that executes daily at 07:00.
- **Network Access**: If ABBYY or webhook integrations are enabled, whitelist the outbound domains
  in the corporate firewall.
- **Data Handling**: Confirm attachments stored under `work/attachments/` comply with retention
  policies. Apply encryption-at-rest if mandated.

## Operational Notes
- The automation stores logs in `logs/` and outputs in `work/`.
- Credentials must never be stored in source files. Use environment variables or Windows Credential
  Manager (`REQUIRES_SECRETS_HANDLING`).
- If New Outlook is detected, run `python -m inbox_reader --dry-run` to confirm the failure message
  and engage IT for switching back to Classic Outlook.

## Developer Notes
- Switch the OCR provider inside `report_builder.py` by replacing `pick_ocr_adapter` with
  `prefer_abbyy=True` and wiring `AbbyyOCRAdapter.extract_text` to the ABBYY SDK client.
- Install Tesseract OCR via `winget install tesseract-ocr` or download the official installer and add
  the binary path to the system `PATH` environment variable.

## Task Scheduler (PowerShell Registration Example)
Run in an elevated PowerShell session after Python is on the PATH:

```powershell
SCHTASKS /Create `
    /TN "OutlookAutoReportDaily" `
    /TR "python %CD%\report_builder.py" `
    /SC DAILY `
    /ST 07:00 `
    /RL HIGHEST `
    /F
```
