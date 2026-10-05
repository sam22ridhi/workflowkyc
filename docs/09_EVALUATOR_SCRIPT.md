# Script: explaining the Sharma Foods case to the evaluators

For the two presenters, to be spoken. About 13 minutes at a steady pace. **[CLICK]** is something you do on screen; *italics* are things to point at. Speak the quoted lines in your own words, but keep the facts and numbers.
P1 = presenter 1 (drives the screen), P2 = presenter 2 (explains). Swap as you like.

Every document you will show is a watermarked synthetic specimen. Say that once, early.

---

## 1. The problem, in 40 seconds

**P2:** "A company that goes live on Paytm's gateway starts with just a PAN and a bank account, capped at fifty thousand rupees a month. To lift the cap, someone has to check a full document set by hand: do the names match across documents, is the person signing actually a director, who really owns more than ten percent, does the bank account belong to the company. Today that is emails, WhatsApp and calls, and a mismatch found late costs another round trip while the merchant stays capped."

**P1:** "So we built a small team of AI teammates that does the document work, and a human who only decides. Our rule: **the model reads, code checks, the model explains, a human approves.** Nothing in the middle is a black box."

## 2. The team, in 30 seconds

**P2:** "Seven teammates. n8n, which we call Sutradhar, is the conductor. Sarvam reads documents and speaks Hindi. Plain Python rules do every pass-or-fail. Cognee is the memory of each merchant. A voice agent chases the merchant. Drishti verifies the shop. A settlement agent watches after go-live. Two humans decide: the account manager, the KAM, and Compliance."

## 3. The Sharma Foods case: who they are

**P1:** *[Show the KAM dashboard, Sharma Foods row]* "Sharma Foods Private Limited, a Mumbai food manufacturer. It is a **private limited company**, and that matters, because the entity type decides what we ask for and which rules apply. I'll come back to that."

**P2:** "We built this case with four realistic problems planted in the paperwork, the kind a KAM really finds. Let's see whether the system finds them."

## 4. The merchant uploads, and document intelligence starts

**P1:** **[CLICK]** *Merchant portal, Upload documents: drop the nine PDFs.* "The merchant just drops files. Each file gets a fingerprint, a SHA-256, so it can never silently change, and Karyakarta works out the document type from the slot, the filename and, if needed, the content."

**P2:** *[Point at the timeline filling in on the KAM screen]* "Now the pipeline runs, orchestrated by n8n. Here is what 'document intelligence' means in our system, step by step."

1. **"Read, with a schema per document type."** "We don't just OCR. For each type of document we tell Sarvam exactly which fields to return: for the GST certificate the GSTIN, legal name, trade name and principal place of business; for the board resolution the authorised signatory and their designation; for the shareholding declaration every shareholder and every partner of a corporate shareholder. Every value comes back with a **confidence** and the **page** it came from."
2. **"Locate, so a human can verify."** "A second pass finds where on the page each value sits, so every value gets a box on the real PDF. A KAM can click a finding and see the exact words highlighted. Tables are boxed at table level, because Sarvam gives no cell coordinates and we won't pretend otherwise."
3. **"Validate each document by itself."** "Format rules: the GSTIN and CIN patterns, IFSC, the FSSAI number, a masked Aadhaar, and shareholding that must add up to one hundred percent."
4. **"Remember."** "A structured summary of each document goes into that merchant's own Cognee graph, through n8n's native Cognee node. That graph is the merchant's digital twin."

**P1:** "Roughly a minute and a half end to end with live services. No human has touched anything."

## 5. The business rules: how entity type drives everything

**P2:** *[Open the case; point at the checks list]* "Now the business rules. They are plain Python, written out and testable, and they depend on the **type of entity**."

| Rule | What the system does |
|---|---|
| **Which documents are required** | A **private or public limited company** and an **LLP** need PAN, GST, certificate of incorporation, **board resolution**, cancelled cheque, director KYC and a **shareholding declaration**. A **partnership or proprietorship** needs only PAN, GST, a cheque and KYC. A food business also needs an **FSSAI licence**. |
| **PAN must fit the entity** | The fourth letter of a PAN encodes the holder type: **C** for a company, **F** for a firm or LLP, **P** for an individual or proprietor. Sharma's is AABC**S**…: fourth character C, a company. A mismatch is flagged. |
| **CIN** | A company has a 21-character CIN that must match the certificate, the application and the MCA record, and the company must be Active. An LLP, partnership or proprietorship has no CIN, so that check is skipped, not failed. |
| **GSTIN** | Fifteen characters, and characters three to twelve must equal the company PAN. It must be Active in the GST registry. |
| **Beneficial owners above ten percent** | Applies to companies and LLPs. We look **through** corporate shareholders to the real people. |
| **Authorised signatory** | The person named in the board resolution must be a **current director** per the MCA record. |

**P1 (if asked about private versus public):** "Honestly: for the documents we require and the ownership rule, private and public limited companies are treated the same today. What differs is the registry data we compare against. A listed company's special cases, like public shareholders and exemptions, are not built, and we say so. The structure is there: it is one table of rules per entity type, so adding that is a configuration change, not a redesign."

## 6. Conflict finding: the four problems, one by one

**P2:** "There are ten cross-document checks. Each returns pass, fail or warn, with its **evidence**: which document, which field, which page, which value. And each failure is routed: **ask** if the merchant can fix it, **escalate** if a person has to judge. Sharma comes back **ESCALATE**: six checks pass, four fail. Let's walk the four."

**P1:** **[CLICK]** *Finding 1: the signatory.* 
**P2:** "The board resolution authorises **Ravish Sahay** as authorised signatory. The MCA record lists two directors: Anil Sharma and Priya Sharma. Ravish is not a director. Note what we do **not** do: we don't reject. A company can validly delegate authority by board resolution, so this is exactly where code stops and a human judges. It is marked **escalate**. The resolution itself is signed by Anil and Priya, and we show that too."

**P1:** **[CLICK]** *Finding 2: the hidden owner. Click the evidence chip so the PDF opens with the value boxed.* 
**P2:** "The shareholding declaration shows Anil forty percent, Priya thirty, and **Sharma Holdings LLP thirty percent**. An LLP is not a person. Its partners are Rakesh sixty and Meera forty. So Rakesh effectively owns sixty percent of thirty: **eighteen percent**, and Meera twelve. Both are above ten percent, neither has KYC on file, and the first one is hidden behind an entity. We compute that look-through, and we escalate. Exactly ten percent would not trigger it; the rule is *more than* ten, and it is tested."

**P1:** *Finding 3: the bank name.* 
**P2:** "The cancelled cheque is pre-printed **Sharma Foods**. The legal name is **Sharma Foods Private Limited**. For general name checks we tolerate 'Pvt' versus 'Private'. For the settlement account we are strict, because the account holder must match exactly. This one the merchant can fix, so it is **ask**. We also compare the account number with the bank's penny-drop record. We once saw Sarvam misread an account number at one hundred percent confidence because a stamp covered digits. **Confidence is not accuracy**, so the second source catches it."

**P1:** *Finding 4: the address.* 
**P2:** "The GST certificate, the FSSAI licence and the electricity bill all say **Navi Mumbai**. The application and the certificate of incorporation say **Mumbai**. We compare the principal place of business and the registered office separately, and only flag real drift. Merchant can fix: **ask**."

**P1:** **[CLICK]** *MAF (Merchant Application Form).* "The same data fills a twenty-field CRM form. Every field shows its source, for example 'GST certificate, page one', its confidence, and a **conflict note** where two sources disagree. If the KAM overrides a value, we keep the AI's original and audit it."

**P2:** **[CLICK]** *Ask this case:* "Who owns more than ten percent of Sharma Foods?" "This is Cognee answering from the merchant's graph, and it names the source documents. Cognee explains. It never decides pass or fail."

## 7. The voice call

**P1:** **[CLICK]** *Voice Chase.* 
**P2:** "The KAM does not want to spend an afternoon chasing. The drawer shows exactly what the agent will say, in Hindi, and what it will **not**. Only the issues the merchant can fix are sent: the cheque name, the address, the missing KYC. The signatory and the hidden owner are **held back for the KAM** and never reach the agent."

**P1:** **[CLICK]** *Call now, or play the rehearsal.* "A Sarvam voice agent calls over a connected phone number. It speaks Hindi, switches to the merchant's language, refuses OTPs and card numbers, promises nothing about approval, and says the account manager will explain anything else. We tested it with a scripted merchant in seven situations: busy, wrong number, asks for English, asks when it will be approved, offers an OTP, and so on."

**P2:** "When the call ends, the outcome, the transcript and the summary land on the case timeline and into the merchant's Cognee memory, so the KAM can later ask 'what did the merchant say?'. To be straightforward: the agent is verified; a real outbound call to a real merchant is the part we rehearse on the day."

## 8. The merchant fixes what they can; the KAM stays in control

**P1:** **[CLICK]** *Trash icon next to the cheque, then the merchant uploads the corrected cheque and the KYC of Priya, Rakesh and Meera.* 
**P2:** "The KAM can delete a submitted file: the checks re-run, the file leaves the merchant's memory, and the merchant can upload again. They upload a corrected cheque in the full legal name and the owners' KYC. The bank and the owner findings clear. The **signatory and the address stay**, because those need judgement. We resolve what is mechanical and we leave the human the rest. The KAM then approves and forwards, with a confirmation because the case is still ESCALATE."

## 9. Four eyes, then the shop, then the video call

**P1:** **[CLICK]** *Switch to Compliance.* "A second person, Compliance, approves. The server enforces it: the agent and the merchant get a refusal if they try to approve, and Compliance can act only after the KAM has submitted."

**P2:** "Then **Drishti**. The merchant gets a secure, camera-only link in their communication centre, not a WhatsApp. Two live photos with GPS. Drishti reads the **signboard**, in Hindi or English, and compares it with the GST trade name, measures the distance to the declared address, and checks the capture is live. If every hard check passes it issues **CPV_VERIFIED** by itself. If anything is doubtful it never fails the shop: it goes to a person."

**P1:** **[CLICK]** *Upload the Hindi-signboard photo, then the counter photo, send.* "The Hindi sign is read as शर्मा फूडस, transliterated, and matched to 'Sharma Foods'."

**P2:** "Then **V-CIP**. RBI needs an authorised human on a video call. We prepare it: a Hindi pre-interview with randomised liveness questions, and the official signs off in one click with the answers, the transcript, the selfie and the ID side by side. We do **not** match faces; a human compares them."

## 10. After go-live: the Settlement Agent

**P1:** **[CLICK]** *Open Annapurna Sweets, Settlements tab.* "Onboarding is where fraud enters. Settlement is where money leaves. This merchant has thirty days of normal settlement around forty thousand rupees a day."
**[CLICK]** *Inject spike, then Run settlement check.*

**P2:** "Two fixed thresholds start it: volume above one hundred fifty percent of the thirty-day baseline, or expected and actual settlement more than ten percent apart. Watch the timeline: **monitor, reconcile, investigate, create case, escalate**. It pulls the merchant's declared profile from Cognee, a single outlet in Pune, finds the specific payments, from a new terminal in Jaipur at night from three repeating payers, has Sarvam write a brief with every number checked against the ledger, and opens an investigation case in the same Needs Attention queue. It **recommends**; it never holds or moves money. The KAM resolves or dismisses."

## 11. Close, and the honest list

**P1:** "So that is the Sharma case end to end: read, check against the rules for the entity type, route what a person must judge, chase only what the merchant can fix, and keep watching after go-live. Every decision has evidence, and every approval is a human."

**P2:** "What we have not done: the registries are a labelled mock, there is no authentication and no stored DPDP consent, WhatsApp and email are timeline entries, Drishti has not been used on a real phone or storefront, there is no face matching, and the settlement agent runs on a synthetic ledger with no scheduler. We would rather you hear it from us."

---

## If an evaluator asks

| Question | Short answer |
|---|---|
| "Why not let the model decide pass or fail?" | Because the answer must be repeatable and explainable to a compliance team. The model reads and explains; fixed rules decide, and every result lists its evidence. |
| "What if Sarvam misreads?" | Every value has a confidence and a page box; a second source (the bank's penny-drop) caught a 100%-confidence misread; and the KAM can override with an audit trail. |
| "Private versus public company?" | Same documents and ownership rule today; the registry data differs; listed-company special cases are not built, and adding them is one rule table. |
| "What if the signatory is a valid employee?" | That is why it escalates instead of failing: a board resolution can delegate authority, so a human judges. |
| "How do you handle layered ownership?" | We look through LLPs and companies using the declared partner table: 60% of 30% is 18%; the rule is *more than* 10%. |
| "Is the voice agent safe?" | Only merchant-fixable items reach it; it refuses OTPs, promises nothing, and hands everything else to the account manager. |
| "Did you measure time saved?" | No. The 3 to 5 days and ₹250 to ₹500 per field visit are the brief's figures for the manual process. |
| "What did you actually run live?" | Upload through n8n with live Sarvam and Cognee, the 10 checks on the planted issues, the voice agent in seven scenarios, Drishti on synthetic photos, and the settlement chain. |
