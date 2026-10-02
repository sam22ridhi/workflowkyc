"""MOCK registry. NOT real MCA21 / GSTN / bank data: a small local stand-in so the cross-document checks have
an "official record" to compare against. All people, numbers and companies here are synthetic.

Per case it returns what the real integrations would: MCA company master (status, registered office, directors,
shareholding), GST status, and a bank penny-drop result (the account holder name the bank returns).
"""
MOCK_LABEL = "MOCK registry (synthetic data, not MCA21 / GSTN / bank)"

_DATA: dict[str, dict] = {
    "KYB-20814": {   # Sharma Foods Private Limited: the hero case
        "mca": {
            "cin": "U56101MH2021PTC123456", "name": "SHARMA FOODS PRIVATE LIMITED", "status": "Active",
            "incorporated": "14/08/2021", "registered_office": "12 MG Road, Mumbai - 400001, Maharashtra",
            "directors": [{"name": "Anil Sharma", "din": "08492019"}, {"name": "Priya Sharma", "din": "08492020"}],
            "shareholding": [
                {"holder": "Anil Sharma", "type": "individual", "percent": 40},
                {"holder": "Priya Sharma", "type": "individual", "percent": 30},
                {"holder": "Sharma Holdings LLP", "type": "llp", "percent": 30},
            ],
        },
        "gst": {"gstin": "27AABCS1429E1Z8", "legal_name": "SHARMA FOODS PRIVATE LIMITED", "trade_name": "Sharma Foods",
                "principal_place": "12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra", "status": "Active"},
        "penny_drop": {"account_number": "50200034928174", "ifsc": "HDFC0000128", "account_holder": "SHARMA FOODS PRIVATE LIMITED",
                       "status": "SUCCESS"},
    },
    "KYB-20815": {
        "mca": {"cin": "AAB-1234", "name": "BHARAT AGRI LOGISTICS LLP", "status": "Active", "incorporated": "03/02/2020",
                "registered_office": "Plot 14, GIDC Estate, Vadodara - 390010, Gujarat",
                "directors": [{"name": "Kiran Patel", "din": "09112233"}, {"name": "Mehul Shah", "din": "09112244"}],
                "shareholding": [{"holder": "Kiran Patel", "type": "individual", "percent": 55},
                                 {"holder": "Mehul Shah", "type": "individual", "percent": 45}]},
        "gst": {"gstin": "24AAJFB5521K1Z2", "legal_name": "BHARAT AGRI LOGISTICS LLP", "trade_name": "Bharat Agri",
                "principal_place": "Plot 14, GIDC Estate, Vadodara - 390010, Gujarat", "status": "Active"},
        "penny_drop": {"account_number": "917020045551230", "ifsc": "UTIB0001870", "account_holder": "BHARAT AGRI LOGISTICS LLP", "status": "SUCCESS"},
    },
    "KYB-20816": {
        "mca": {"cin": "U72900KA2019PTC128765", "name": "ZENITH TECHNOLOGIES PRIVATE LIMITED", "status": "Active",
                "incorporated": "21/06/2019", "registered_office": "4th Floor, Embassy Tech Square, Bengaluru - 560103, Karnataka",
                "directors": [{"name": "Neha Rao", "din": "08811200"}, {"name": "Vikram Iyer", "din": "08811201"}],
                "shareholding": [{"holder": "Neha Rao", "type": "individual", "percent": 60},
                                 {"holder": "Vikram Iyer", "type": "individual", "percent": 40}]},
        "gst": {"gstin": "29AABCZ3310M1Z5", "legal_name": "ZENITH TECHNOLOGIES PRIVATE LIMITED", "trade_name": "Zenith Tech",
                "principal_place": "4th Floor, Embassy Tech Square, Bengaluru - 560103, Karnataka", "status": "Active"},
        "penny_drop": {"account_number": "002201987654", "ifsc": "ICIC0000022", "account_holder": "ZENITH TECHNOLOGIES PRIVATE LIMITED", "status": "SUCCESS"},
    },
    "KYB-20817": {
        "mca": None,   # proprietorship: no MCA record
        "gst": {"gstin": "08BKQPS7788L1ZP", "legal_name": "ROYAL RAJASTHAN SPICES", "trade_name": "Royal Rajasthan Spices",
                "principal_place": "Johari Bazaar, Jaipur - 302003, Rajasthan", "status": "Active"},
        "penny_drop": {"account_number": "31245098877", "ifsc": "SBIN0004567", "account_holder": "SURESH KUMAR SAINI", "status": "SUCCESS"},
    },
    "KYB-20818": {
        "mca": {"cin": "L64200DL2012PLC241903", "name": "APEX CLOUD TELECOM LIMITED", "status": "Active", "incorporated": "11/11/2012",
                "registered_office": "Tower B, Nehru Place, New Delhi - 110019",
                "directors": [{"name": "Arjun Malhotra", "din": "05566001"}, {"name": "Sunita Verma", "din": "05566002"},
                              {"name": "Rohit Khanna", "din": "05566003"}],
                "shareholding": [{"holder": "Arjun Malhotra", "type": "individual", "percent": 35},
                                 {"holder": "Public shareholders", "type": "public", "percent": 65}]},
        "gst": {"gstin": "07AAACA9087D1Z9", "legal_name": "APEX CLOUD TELECOM LIMITED", "trade_name": "Apex Cloud",
                "principal_place": "Tower B, Nehru Place, New Delhi - 110019", "status": "Active"},
        "penny_drop": {"account_number": "0450112233445", "ifsc": "KKBK0000203", "account_holder": "APEX CLOUD TELECOM LIMITED", "status": "SUCCESS"},
    },
}


def lookup(case_id: str) -> dict:
    """Registry record for a case (empty parts when the registry has nothing). Always carries the MOCK label."""
    rec = _DATA.get(case_id, {})
    return {"label": MOCK_LABEL, "mca": rec.get("mca"), "gst": rec.get("gst"), "penny_drop": rec.get("penny_drop")}
