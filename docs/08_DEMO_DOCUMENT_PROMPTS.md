# Prompts to generate the Sharma Foods demo documents with an image or document generator

You do not need these to run the demo: `python -m seed.make_realistic_docs` already creates a nine-document pack (and a four-document fix pack) as real PDFs with a text layer, and the recorded Sarvam results match those exact files.
Use the prompts below only if you want a different look. Two things to know first:

* A generated **image** has no text layer and generators often garble numbers. Ask for a PDF or high-resolution scan, then check **every number** against the table below before you upload, because the checks compare them character by character.
* Keep the safety wording in the master prompt. Documents that imitate government papers must stay obviously synthetic.

## Master prompt (paste first, then one document prompt)

> You are producing a **synthetic specimen document for a software demonstration**. It must look like the paperwork a bank officer would receive in India, but it must be **unmistakably fake**:
> * Add a large, light diagonal watermark across the page reading **SPECIMEN - SYNTHETIC DEMO DATA** and a small footer line: "Synthetic specimen created for a software demonstration. Fictional names and numbers. Not a valid document."
> * Do **not** reproduce any government emblem, logo, hologram, QR code, barcode, seal of a real authority, or any security feature. Use a plain typographic header instead.
> * Use only the names and numbers I give you, **exactly as written, character for character**. Do not invent or alter any identifier, date, address or amount.
> * Realistic layout: A4 portrait, proper margins, a clean official-looking template for this kind of document, crisp black text with the labels in grey, ruled tables where the real document has them, a blue-ink signature scribble and a round blue company seal where one would appear, and a "CERTIFIED TRUE COPY" stamp only where I ask. No photographs of real people: use a plain grey silhouette.
> * Output a single-page, high-resolution PDF (or a 300 dpi PNG) of a clean flat scan: no perspective, no shadows, no handwriting except signatures.
> Company throughout: **SHARMA FOODS PRIVATE LIMITED** (trade name "Sharma Foods"), a Mumbai food manufacturer.

## The facts (use exactly)

| Item | Value |
|---|---|
| Legal name | SHARMA FOODS PRIVATE LIMITED |
| CIN | U56101MH2021PTC123456 |
| PAN (company) | AABCS1429E |
| GSTIN | 27AABCS1429E1Z8 |
| Date of incorporation | 14/08/2021 |
| Registered office (in the application and the COI) | 12 MG Road, Mumbai - 400001, Maharashtra |
| Principal place of business (GST, FSSAI, electricity bill) | 12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra |
| Directors | Anil Sharma (DIN 08492019), Priya Sharma (DIN 08492077) |
| Bank | HDFC Bank, Fort Branch, Mumbai - 400001; account 50200034928174; IFSC HDFC0000128; Current account |

The four planted problems must stay exactly as written, they are the point of the demo:
1. the cheque is pre-printed **Sharma Foods** (not "Sharma Foods Private Limited");
2. the board resolution authorises **Ravish Sahay**, who is not a director;
3. **Sharma Holdings LLP** holds 30% and its partners are Rakesh Sharma 60% and Meera Sharma 40% (so 18% and 12% effective owners);
4. GST, FSSAI and the electricity bill say **Navi Mumbai** while the COI and application say **Mumbai**.

## One prompt per document

**1. Company PAN card** (landscape card on an A4 page)
> Using the master prompt: a company PAN card specimen, card-style with a blue header band "INCOME TAX DEPARTMENT" and the words "Permanent Account Number Card (specimen format)". Fields: Permanent Account Number **AABCS1429E**; Name **SHARMA FOODS PRIVATE LIMITED**; Date of Incorporation / Formation **14/08/2021**; a signature box with a scribble.

**2. GST registration certificate**
> Using the master prompt: a "Form GST REG-06, [See Rule 10(1)], REGISTRATION CERTIFICATE" in a bordered table. Registration Number **27AABCS1429E1Z8**; 1 Legal Name **SHARMA FOODS PRIVATE LIMITED**; 2 Trade Name **Sharma Foods**; 3 Constitution of Business **Private Limited Company**; 4 Address of Principal Place of Business **12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra**; 5 Date of Liability **04/08/2021**; 6 Period of Validity **From 04/08/2021 To Not Applicable**; 7 Type of Registration **Regular Taxpayer**; additional places of business: Nil; date of issue 06/08/2021; "Digitally signed, Proper Officer" with a scribble.

**3. Certificate of Incorporation**
> Using the master prompt: a formal Certificate of Incorporation with a double gold-brown border and the heading "Ministry of Corporate Affairs / Office of the Registrar of Companies, Mumbai". Text: "I hereby certify that SHARMA FOODS PRIVATE LIMITED is this day incorporated under the Companies Act, 2013 (18 of 2013) and that the company is a Private Limited Company." Corporate Identity Number **U56101MH2021PTC123456**; PAN **AABCS1429E**; date of incorporation **14/08/2021**; Registered Office **12 MG Road, Mumbai - 400001, Maharashtra**; "Given at Mumbai this Fourteenth day of August Two Thousand Twenty-One"; Registrar signature scribble and a round blue seal.

**4. Certified board resolution** (company letterhead)
> Using the master prompt: a company-letterhead "CERTIFIED TRUE COPY OF THE RESOLUTION PASSED BY THE BOARD OF DIRECTORS" for SHARMA FOODS PRIVATE LIMITED (letterhead shows CIN and registered office), meeting on **02/09/2026** at the registered office. Three numbered clauses: open and operate a merchant account with Paytm Payment Gateway; **Mr. Ravish Sahay, Authorised Signatory** is authorised to sign all applications and agreements; a certified copy may be furnished. A small "Specimen of the Authorised Signatory" table: Ravish Sahay, Authorised Signatory, signature scribble, PAN BQRPS4410K. Signed by Directors **Anil Sharma (DIN 08492019)** and **Priya Sharma (DIN 08492077)** with scribbles, a blue company seal and a red "CERTIFIED TRUE COPY" stamp.

**5. Cancelled cheque**
> Using the master prompt: a scanned cancelled cheque leaf, "HDFC BANK, Fort Branch, Mumbai - 400001", date boxes, PAY / RUPEES lines and an amount box left blank, a blue "CANCELLED" stamp and two crossing lines placed **away from** the printed details. Pre-printed: A/c Name **Sharma Foods**; A/c No. **50200034928174**; IFSC **HDFC0000128**; Account Type **Current**; an "Authorised Signatory" line; a MICR band at the bottom. Do not use the real HDFC logo: a plain red square mark.

**6. Director identity card, masked** (with a DIN block)
> Using the master prompt: a masked identity card specimen, orange header "UNIQUE IDENTITY CARD (specimen layout)", grey silhouette instead of a photo. Name **Anil Sharma**; Date of Birth **09/03/1978**; Male; Address **12 MG Road, Mumbai - 400001, Maharashtra**; number printed as **XXXX XXXX 4821**. Below it a small table: Director name Anil Sharma, **DIN 08492019**, date of allotment 21/06/2021, Status Approved.

**7. Shareholding and beneficial-ownership declaration**
> Using the master prompt: company-letterhead "DECLARATION OF SHAREHOLDING AND BENEFICIAL OWNERSHIP, as of 01/09/2026". Table A, direct shareholders: Anil Sharma, Individual, 4,000 shares, **40%**; Priya Sharma, Individual, 3,000, **30%**; **Sharma Holdings LLP**, LLP, 3,000, **30%**; total 10,000, 100%. Table B, partners of Sharma Holdings LLP: **Rakesh Sharma 60%**, **Meera Sharma 40%**. A short declaration paragraph, Anil Sharma's signature scribble, blue company seal.

**8. FSSAI licence**
> Using the master prompt: a green-header "FOOD SAFETY AND STANDARDS ACT, 2006, Licence for Food Business Operator (specimen format)". Licence No. **11521999000123**; name **SHARMA FOODS PRIVATE LIMITED**; premises **12 Mahatma Gandhi Marg, Navi Mumbai - 400703**; Licence Type **State Licence**; Kind of Business **Manufacturer**; valid from **10/10/2025** until **09/10/2030**; designated officer scribble and round seal.

**9. Electricity bill** (address proof)
> Using the master prompt: a commercial electricity bill from a **fictional** utility, "WESTERN POWER DISTRIBUTION COMPANY LIMITED". Consumer Name **SHARMA FOODS PRIVATE LIMITED**; Consumer Number **170240055310**; Service Address **12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra**; Bill Date **05/09/2026**; Due Date 20/09/2026; billing period 05/08/2026 to 04/09/2026; a charges table (energy 1,842 kWh, fixed charges, taxes, total Rs. 21,048.80).

## Fix pack (Act 5 of the runbook)

* **Corrected cheque:** same as document 5 with A/c Name **SHARMA FOODS PRIVATE LIMITED**.
* **Identity cards for the other owners:** same as document 6 for **Priya Sharma** (DOB 22/11/1981, XXXX XXXX 7733, DIN 08492077), **Rakesh Sharma** (DOB 03/05/1975, XXXX XXXX 5590) and **Meera Sharma** (DOB 17/09/1979, XXXX XXXX 3318); for Rakesh and Meera replace the DIN table with "Beneficial owner identification: Partner of Sharma Holdings LLP".

## After generating

Save with the same filenames as `backend/seed/demo_pack/` is *not* required, but the file name should still contain the document kind (`PAN`, `GST`, `Incorporation`, `Board`, `Cheque`, `KYC`, `Shareholding`, `FSSAI`, `Electricity`) so Karyakarta can classify it. Generated files will have **no recorded Sarvam result**, so they need live Sarvam credit when read; run `seed.bat --refresh-cache` once to record them.
