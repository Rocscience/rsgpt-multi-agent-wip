# Your existing global dicts
ROCSCIENCE = {"domain_name": "ROCSCIENCE.COM", "registrar":  "Network Solutions, LLC"}
DIANNA = {"domain_name": "DIANAFEA.COM", "registrar":  "TUCOWS, INC."}
DIANNA_ALT = {"domain_name": "dianafea.com", "registrar":  "tucows domains inc."}
THREEGSM = {"domain_name": "3gsm.at", "registrar":  "T-Mobile Austria GmbH ( https://nic.at/registrar/60 )"}

# Source to URL mappings for media extraction
SOURCE_URLS = {
    "ROC": "https://www.rocscience.com",
    "DIANA": "https://www.dianafea.com",
    "3GSM": "https://www.3gsm.at",
    "2SI": "https://www.2si.at",
    "ROCKFIELD": "https://www.rockfieldglobal.com"
}

# Collect all uppercase global dicts safely by iterating over a copy of globals
whitelisted_dicts = []
for name, value in list(globals().items()):  # <-- here: use list() to copy
    if not name.startswith("__") and name.isupper():
        # Convert all values in the dictionary to lowercase
        lowercased_dict = {k: v.lower() for k, v in value.items()}
        whitelisted_dicts.append(lowercased_dict)

WHITELIST = whitelisted_dicts
