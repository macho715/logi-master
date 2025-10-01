# Kutools Advanced Rules

The following six rules can be entered into Kutools for Outlook → Advanced Rules. Each rule uses
"Move to Folder" as the recommended action, targeting the default Auto-Reports flow. Adjust folder
names to match your tenant if required.

## 1. Invoice Routing
1. Rule name: `AutoReport - Invoice`
2. Apply to: `Subject` contains `invoice` OR `Attachment name` contains `.pdf`
3. Condition: `Sender` contains `accounts@` OR `finance`
4. Action: Move to folder `Auto/Inbox/Auto-Reports`
5. Optional: Flag message for follow-up in 1 day.

## 2. Packing List (PL) Capture
1. Rule name: `AutoReport - PL`
2. Apply to: `Subject` contains `packing list` OR `Subject` contains `PL`
3. Condition: `Body` contains `HS code` OR `Body` contains `carton`
4. Action: Move to folder `Auto/Inbox/Auto-Reports`
5. Optional: Assign category `PL`

## 3. Vendor Scorecards
1. Rule name: `AutoReport - Vendor`
2. Apply to: `Subject` contains `vendor` OR `Subject` contains `scorecard`
3. Condition: `Sender` domain contains `@supplier.`
4. Action: Move to folder `Auto/Inbox/Auto-Reports`
5. Optional: Mark as read.

## 4. OTIF Alerts
1. Rule name: `AutoReport - OTIF`
2. Apply to: `Subject` contains `OTIF` OR `Body` contains `On time in full`
3. Condition: `Importance` equals `High`
4. Action: Move to folder `Auto/Inbox/Auto-Reports`
5. Optional: Add category `OTIF`

## 5. URGENT Escalations
1. Rule name: `AutoReport - URGENT`
2. Apply to: `Subject` contains `URGENT` OR `Subject` contains `ACTION REQUIRED`
3. Condition: `Sender` domain contains `@logistics.`
4. Action: Move to folder `Auto/Inbox/Auto-Reports`
5. Optional: Forward to escalation mailbox (confirm with IT policy).

## 6. Industry News Digest
1. Rule name: `AutoReport - NEWS`
2. Apply to: `Subject` contains `news` OR `Body` contains `market update`
3. Condition: `Sender` domain contains `@newsletter.` OR `@insights.`
4. Action: Move to folder `Auto/Inbox/Auto-Reports`
5. Optional: Assign category `NEWS`
