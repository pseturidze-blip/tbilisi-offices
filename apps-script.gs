/**
 * საიდუმლო სანტა — პირადი ბმულების ავტომატური გაგზავნა Gmail-იდან
 *
 * დაყენება:
 *  1. გახსენით https://script.google.com და დააჭირეთ „New project“ (ახალი პროექტი).
 *  2. წაშალეთ რედაქტორში არსებული კოდი და ჩასვით ამ ფაილის მთლიანი შიგთავსი.
 *  3. ქვემოთ SECRET_TOKEN-ში ჩაწერეთ საკუთარი საიდუმლო ტოკენი — გრძელი, შემთხვევითი
 *     სტრიქონი (მაგ. 30+ სიმბოლო). იგივე ტოკენი ჩაწერეთ გვერდზე, ველში „საიდუმლო ტოკენი“.
 *  4. შეინახეთ პროექტი (Ctrl+S).
 *  5. დააჭირეთ Deploy → New deployment.
 *  6. ⚙ ხატულაზე აირჩიეთ ტიპი „Web app“.
 *  7. Execute as: „Me“ (მეილები თქვენი ანგარიშიდან გაიგზავნება).
 *  8. Who has access: „Anyone“.
 *  9. Deploy → დაადასტურეთ ნებართვები (Google მოგთხოვთ, დაუშვათ მეილის გაგზავნა თქვენი სახელით).
 * 10. დააკოპირეთ Web App URL (მთავრდება /exec-ით) და ჩასვით გვერდზე, ველში
 *     „Apps Script-ის ვებ-აპლიკაციის მისამართი (URL)“.
 *
 * შენიშვნები:
 *  - კოდის შეცვლის შემდეგ: Deploy → Manage deployments → ✏️ → Version: „New version“ → Deploy.
 *  - Gmail-ის ჩვეულებრივ ანგარიშს დღეში დაახლოებით 100 მეილის გაგზავნა შეუძლია.
 *  - მეილებში მხოლოდ მონაწილის სახელი და მისი პირადი ბმულია — ვის ვინ ხვდება, არსად ჩანს.
 *  - გაგზავნის შედეგი ნახეთ: Executions (შესრულებები) მენიუში ან Gmail-ის „გაგზავნილებში“.
 */

const SECRET_TOKEN = 'CHANGE_ME';

const MAX_RECIPIENTS = 100;
const SENDER_NAME = 'საიდუმლო სანტა';
const EMAIL_SUBJECT = '🎅 საიდუმლო სანტა — შენი პირადი ბმული';
const EMAIL_RE = /^[A-Za-z0-9.!#$%&'*+\/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$/;

function doPost(e) {
  try {
    if (!SECRET_TOKEN || SECRET_TOKEN === 'CHANGE_ME') {
      console.error('SECRET_TOKEN არ არის დაყენებული — გაგზავნა გამორთულია.');
      return done_();
    }

    const data = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (data.token !== SECRET_TOKEN) return done_(); // wrong token: exit silently

    const emails = Array.isArray(data.emails) ? data.emails.slice(0, MAX_RECIPIENTS) : [];
    const budget = str_(data.budget, 100);
    const note = str_(data.note, 500);

    const quota = MailApp.getRemainingDailyQuota();
    if (quota < emails.length) {
      console.error('დღიური ლიმიტი არ კმარა: დარჩენილია ' + quota + ', საჭიროა ' + emails.length + '.');
    }

    let sent = 0;
    let failed = 0;
    emails.forEach(function (item, i) {
      const to = str_(item && item.to, 254).trim();
      const name = str_(item && item.name, 200).trim();
      const link = str_(item && item.link, 2000).trim();

      if (!EMAIL_RE.test(to) || !name || !/^https?:\/\/\S+$/.test(link)) {
        failed++;
        console.error('მიმღები #' + (i + 1) + ': არასწორი მონაცემები, გამოტოვებულია.');
        return;
      }

      const content = { name: name, link: link, budget: budget, note: note };
      try {
        MailApp.sendEmail({
          to: to,
          subject: EMAIL_SUBJECT,
          body: buildEmailBody_(content),
          htmlBody: buildEmailHtml_(content),
          name: SENDER_NAME,
        });
        sent++;
      } catch (err) {
        failed++;
        console.error('მიმღები #' + (i + 1) + ': ვერ გაიგზავნა — ' + (err && err.message));
      }

      if (i < emails.length - 1) Utilities.sleep(300);
    });

    console.log('გაიგზავნა: ' + sent + ', შეცდომა: ' + failed + (data.emails && data.emails.length > MAX_RECIPIENTS ? ', ზღვარს გადაცილებული გამოტოვდა: ' + (data.emails.length - MAX_RECIPIENTS) : ''));
    return done_();
  } catch (err) {
    console.error('doPost: ' + (err && err.message));
    return done_();
  }
}

/* Same wording as buildEmailBody() in secret-santa.html — keep them in sync. */
function buildEmailBody_(c) {
  const lines = [
    'გამარჯობა, ' + c.name + '! 🎅',
    '',
    'ვთამაშობთ საიდუმლო სანტას — ბმულზე გაიგებ, ვისთვის ირჩევ საჩუქარს.',
    '',
    'შენი პირადი ბმული:',
    c.link,
  ];
  if (c.budget || c.note) lines.push('');
  if (c.budget) lines.push('ბიუჯეტი: ' + c.budget);
  if (c.note) lines.push('შენიშვნა: ' + c.note);
  lines.push('', 'ბმული არავის გაუზიარო 🤫');
  return lines.join('\n');
}

function buildEmailHtml_(c) {
  const link = esc_(c.link);
  let html =
    '<div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.6;color:#1b2620">' +
    '<p>გამარჯობა, <strong>' + esc_(c.name) + '</strong>! 🎅</p>' +
    '<p>ვთამაშობთ საიდუმლო სანტას — ბმულზე გაიგებ, ვისთვის ირჩევ საჩუქარს.</p>' +
    '<p><a href="' + link + '" style="display:inline-block;background:#b3202e;color:#ffffff;text-decoration:none;font-weight:bold;padding:12px 20px;border-radius:10px">🎁 შენი პირადი ბმული</a></p>' +
    '<p style="font-size:13px;color:#5d6b63;word-break:break-all">' + link + '</p>';
  if (c.budget) html += '<p><strong>ბიუჯეტი:</strong> ' + esc_(c.budget) + '</p>';
  if (c.note) html += '<p><strong>შენიშვნა:</strong> ' + esc_(c.note).replace(/\n/g, '<br>') + '</p>';
  html += '<p>ბმული არავის გაუზიარო 🤫</p></div>';
  return html;
}

function esc_(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function str_(v, max) {
  return typeof v === 'string' ? v.slice(0, max) : '';
}

function done_() {
  return ContentService.createTextOutput('ok').setMimeType(ContentService.MimeType.TEXT);
}
