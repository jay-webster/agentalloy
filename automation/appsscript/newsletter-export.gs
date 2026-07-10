/**
 * Exports newsletter-shaped Gmail messages to a Drive-hosted JSONL file
 * for the automation pipeline's scheduled-drive-sync routine to import.
 *
 * Runs under your own Google account (deploy via script.google.com — see
 * README.md in this directory). Not part of the Python package; not
 * tested by this repo's pytest/ruff/pyright — there is no way to execute
 * or verify Apps Script code from outside a Google account.
 *
 * Field names in the exported JSON objects must exactly match what
 * automation/cli.py's `ingest import-jsonl` command requires:
 * message_id, thread_id, source, subject, received_at, snippet.
 */

// Maintained separately from the repo's automation/config/sources.yaml —
// Apps Script cannot read files from the local repo. Keep these two lists
// in sync by hand.
var SENDER_ALLOWLIST = [
  'theshiftai@mail.beehiiv.com',
  'stayingahead@mail.beehiiv.com',
  'bayareatimes@bayareatimes.com',
  'hello@every.to',
  'editor@read.ctomode.com',
  'smarterwithai@mail.beehiiv.com',
  'thesimplifiedai@mail.beehiiv.com'
];

var EXPORTED_LABEL_NAME = 'agentalloy-automation-exported';
var EXPORT_FILENAME = 'agentalloy-automation-newsletter-export.jsonl';
var SNIPPET_MAX_CHARS = 500;

function exportNewsletters() {
  var label = GmailApp.getUserLabelByName(EXPORTED_LABEL_NAME) ||
    GmailApp.createLabel(EXPORTED_LABEL_NAME);

  var fromClauses = SENDER_ALLOWLIST.map(function (addr) {
    return 'from:' + addr;
  });
  var query = 'in:inbox {' + fromClauses.join(' ') + '} -label:' + EXPORTED_LABEL_NAME;

  var threads = GmailApp.search(query);
  if (threads.length === 0) {
    return;
  }

  var lines = [];
  for (var t = 0; t < threads.length; t++) {
    var messages = threads[t].getMessages();
    for (var m = 0; m < messages.length; m++) {
      var message = messages[m];
      var row = {
        message_id: message.getId(),
        thread_id: threads[t].getId(),
        source: message.getFrom(),
        subject: message.getSubject(),
        received_at: message.getDate().toISOString(),
        snippet: message.getPlainBody().substring(0, SNIPPET_MAX_CHARS)
      };
      lines.push(JSON.stringify(row));
    }
    threads[t].addLabel(label);
  }

  appendToExportFile(lines);
}

function appendToExportFile(newLines) {
  var files = DriveApp.getFilesByName(EXPORT_FILENAME);
  var content = newLines.join('\n') + '\n';

  if (files.hasNext()) {
    var file = files.next();
    var existing = file.getBlob().getDataAsString();
    file.setContent(existing + content);
  } else {
    DriveApp.createFile(EXPORT_FILENAME, content, MimeType.PLAIN_TEXT);
  }
}
