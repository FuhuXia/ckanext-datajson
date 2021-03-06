import re

# from the iso8601 package, plus ^ and $ on the edges
ISO8601_REGEX = re.compile(r"^([0-9]{4})(-([0-9]{1,2})(-([0-9]{1,2})"
    r"((.)([0-9]{2}):([0-9]{2})(:([0-9]{2})(\.([0-9]+))?)?"
    r"(Z|(([-+])([0-9]{2}):([0-9]{2})))?)?)?)?$")

URL_REGEX = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https:// or ftp:// or ftps://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

ACCRUAL_PERIODICITY_VALUES = (None, "Annual", "Bimonthly", "Semiweekly", "Daily", "Biweekly", "Semiannual", "Biennial", "Triennial", "Three times a week", "Three times a month", "Continuously updated", "Monthly", "Quarterly", "Semimonthly", "Three times a year", "Weekly", "Completely irregular")

LANGUAGE_REGEX = re.compile("^[A-Za-z]{2}([A-Za-z]{2})?$")

# load the OMB bureau codes on first load of this module
import urllib, csv
omb_burueau_codes = set()
for row in csv.DictReader(urllib.urlopen("https://raw.github.com/seanherron/OMB-Agency-Bureau-and-Treasury-Codes/master/omb-agency-bureau-treasury-codes.csv")):
    omb_burueau_codes.add(row["OMB Agency Code"] + ":" + row["OMB Bureau Code"])

# main function for validation
def do_validation(doc, errors_array):
    errs = { }
    
    if type(doc) != list:
        add_error(errs, 0, "Bad JSON Structure", "The file must be an array at its top level. That means the file starts with an open bracket [ and ends with a close bracket ].")
    elif len(doc) == 0:
        add_error(errs, 0, "Catalog Is Empty", "There are no entries in your file.")
    else:
        seen_identifiers = set()
        
        for i, item in enumerate(doc):
            # Required
            
            # title
            dataset_name = "dataset %d" % (i+1)
            if check_string_field(item, "title", 5, dataset_name, errs):
                dataset_name = '"%s"' % item.get("title", "").strip()
                
            # description
            check_string_field(item, "description", 30, dataset_name, errs)
                
            # keyword
            if isinstance(item.get("keyword"), (str, unicode)):
                add_error(errs, 5, "Update Your File!", "The keyword field used to be a string but now it must be an array.", dataset_name)
                
            elif check_required_field(item, "keyword", list, dataset_name, errs):
                for kw in item["keyword"]:
                    if not isinstance(kw, (str, unicode)):
                        add_error(errs, 5, "Invalid Required Field Value", "Each keyword in the keyword array must be a string", dataset_name)
                    elif len(kw.strip()) == 0:
                        add_error(errs, 5, "Invalid Required Field Value", "A keyword in the keyword array was an empty string.", dataset_name)
                    
            # bureauCode
            if check_required_field(item, "bureauCode", list, dataset_name, errs):
                for bc in item["bureauCode"]:
                    if not isinstance(bc, (str, unicode)):
                        add_error(errs, 5, "Invalid Required Field Value", "Each bureauCode must be a string", dataset_name)
                    elif ":" not in bc:
                        add_error(errs, 5, "Invalid Required Field Value", "The bureau code \"%s\" is invalid. Start with the agency code, then a colon, then the bureau code." % bc, dataset_name)
                    elif bc not in omb_burueau_codes:
                        add_error(errs, 5, "Invalid Required Field Value", "The bureau code \"%s\" was not found in our list." % bc, dataset_name)
                
            # modified
            check_date_field(item, "modified", dataset_name, errs)
            
            # publisher
            check_string_field(item, "publisher", 1, dataset_name, errs)
            
            # contactPoint
            check_string_field(item, "contactPoint", 3, dataset_name, errs)
            
            # mbox
            if check_string_field(item, "mbox", 3, dataset_name, errs):
                import lepl.apps.rfc3696
                email_validator = lepl.apps.rfc3696.Email()
                if not email_validator(item["mbox"]):
                    add_error(errs, 5, "Invalid Required Field Value", "The email address \"%s\" is not a valid email address." % item["mbox"], dataset_name)
            
            # identifier
            if check_string_field(item, "identifier", 1, dataset_name, errs):
                if item["identifier"] in seen_identifiers:
                    add_error(errs, 5, "Invalid Required Field Value", "The dataset identifier \"%s\" is used more than once." % item["identifier"], dataset_name)
                seen_identifiers.add(item["identifier"])
                
            # programOffice
            if check_required_field(item, "programOffice", list, dataset_name, errs):
                for s in item["programOffice"]:
                    if not isinstance(s, (str, unicode)):
                        add_error(errs, 5, "Invalid Required Field Value", "Each value in the programOffice array must be a string", dataset_name)
                    elif len(s.strip()) == 0:
                        add_error(errs, 5, "Invalid Required Field Value", "A value in the programOffice array was an empty string.", dataset_name)
                
            # accessLevel
            if check_string_field(item, "accessLevel", 0, dataset_name, errs):
                if item["accessLevel"] not in ("public", "restricted public", "non-public"):
                    add_error(errs, 5, "Invalid Required Field Value", "The field 'accessLevel' had an invalid value: \"%s\"" % item["accessLevel"], dataset_name)
                elif item["accessLevel"] == "non-public":
                    add_error(errs, 1, "Possible Private Data Leakage", "A dataset appears with accessLevel set to \"non-public\".", dataset_name)
            
            # Required-If-Applicable
            
            # accessLevelComment
            if item.get("accessLevel") != "public":
                check_string_field(item, "accessLevelComment", 10, dataset_name, errs)
            
            # accessURL & webService
            check_url_field(False, item, "accessURL", dataset_name, errs)
            check_url_field(False, item, "webService", dataset_name, errs)
            if item.get("accessLevel") == "public" and item.get("accessURL") is None:
                add_error(errs, 20, "Where's the Dataset?", "A public dataset is missing an accessURL.", dataset_name)
            elif item.get("accessURL") is None and item.get("webService") is None:
                add_error(errs, 20, "Where's the Dataset?", "A dataset has neither an accessURL nor a webService.", dataset_name)
            
            # format
            # TODO: MIME yes, but array?
            if item.get("accessURL"):
                check_string_field(item, "format", 1, dataset_name, errs)
                
            # license
            if item.get("license") is not None and not isinstance(item.get("license"), (str, unicode)):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'license' must be a string value if specified.", dataset_name)
            
            # spatial
            # TODO: There are more requirements than it be a string.
            if item.get("spatial") is not None and not isinstance(item.get("spatial"), (str, unicode)):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'spatial' must be a string value if specified.", dataset_name)
                
            # temporal
            if item.get("temporal") is None:
                pass # not required
            elif not isinstance(item["temporal"], (str, unicode)):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'temporal' must be a string value if specified.", dataset_name)
            elif "/" not in item["temporal"]:
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'temporal' must be two dates separated by a forward slash.", dataset_name)
            else:
                d1, d2 = item["temporal"].split("/", 1)
                if not ISO8601_REGEX.match(d1) or not ISO8601_REGEX.match(d2):
                    add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'temporal' has an invalid start or end date.", dataset_name)
            
            # Expanded Fields
            
            # theme
            if item.get("theme") is None:
                pass # not required
            elif not isinstance(item["theme"], list):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'theme' must be an array.", dataset_name)
            else:
                for s in item["theme"]:
                    if not isinstance(s, (str, unicode)):
                        add_error(errs, 50, "Invalid Field Value (Optional Fields)", "Each value in the theme array must be a string", dataset_name)
                    elif len(s.strip()) == 0:
                        add_error(errs, 50, "Invalid Field Value (Optional Fields)", "A value in the theme array was an empty string.", dataset_name)
            
            # dataDictionary
            check_url_field(False, item, "dataDictionary", dataset_name, errs)
            
            # dataQuality
            if item.get("dataQuality") is None:
                pass # not required
            elif not isinstance(item["dataQuality"], bool):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'theme' must be true or false, as a JSON boolean literal (not the string \"true\" or \"false\").", dataset_name)
                
            # distribution
            if item.get("distribution") is None:
                pass # not required
            elif not isinstance(item["distribution"], list):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'distribution' must be an array, if present.", dataset_name)
            else:
                for j, d in enumerate(item["distribution"]):
                    resource_name = dataset_name + (" distribution %d" % (j+1))
                    check_url_field(True, d, "accessURL", resource_name, errs)
                    check_string_field(d, "format", 1, resource_name, errs)
                    # TODO: Check that it's a MIME type.
                
            # accrualPeriodicity
            if item.get("accrualPeriodicity") not in ACCRUAL_PERIODICITY_VALUES:
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'accrualPeriodicity' had an invalid value.", dataset_name)
            
            # landingPage
            check_url_field(False, item, "landingPage", dataset_name, errs)
            
            # language
            if item.get("language") is None:
                pass # not required
            elif not isinstance(item["language"], list):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'language' must be an array, if present.", dataset_name)
            else:
                for s in item["language"]:
                    if not LANGUAGE_REGEX.matches(s):
                        add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'language' had an invalid language: \"%s\"" % s, dataset_name)
                    
            # PrimaryITInvestmentUII
            if item.get("PrimaryITInvestmentUII") is None:
                pass # not required
            elif not isinstance(item["PrimaryITInvestmentUII"], (str, unicode)):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'PrimaryITInvestmentUII' must be a string, if present.", dataset_name)
                
            # references
            if item.get("references") is None:
                pass # not required
            elif not isinstance(item["references"], list):
                add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'references' must be an array, if present.", dataset_name)
            else:
                for s in item["references"]:
                    if not URL_REGEX.match(s):
                        add_error(errs, 50, "Invalid Field Value (Optional Fields)", "The field 'references' had an invalid URL: \"%s\"" % s, dataset_name)
            
            # issued
            if item.get("issued") is not None:
                check_date_field(item, "issued", dataset_name, errs)
            
            # systemOfRecords
            # TODO: No details in the schema!
    
    # Form the output data.
    for err_type in sorted(errs):
        errors_array.append( (
            err_type[1], # heading
            [ err_item + (" (%d locations)" % len(errs[err_type][err_item]) if len(errs[err_type][err_item]) else "")
              for err_item in sorted(errs[err_type], key=lambda x:(-len(errs[err_type][x]), x))
            ]) )
    
def add_error(errs, severity, heading, description, context=None):
    s = errs.setdefault((severity, heading), { }).setdefault(description, set())
    if context: s.add(context)

def nice_type_name(data_type):
    if data_type == (str, unicode) or data_type in (str, unicode):
        return "string"
    elif data_type == list:
        return "array"
    else:
        return str(data_type)

def check_required_field(obj, field_name, data_type, dataset_name, errs):
    # checks that a field exists and has the right type
    if field_name not in obj:
        add_error(errs, 10, "Missing Required Fields", "The '%s' field is missing." % field_name, dataset_name)
        return False
    elif obj[field_name] is None:
        add_error(errs, 10, "Missing Required Fields", "The '%s' field is set to null." % field_name, dataset_name)
        return False
    elif not isinstance(obj[field_name], data_type):
        add_error(errs, 5, "Invalid Required Field Value", "The '%s' field must be a %s but it has a different datatype (%s)." % (field_name, nice_type_name(data_type), nice_type_name(type(obj[field_name]))), dataset_name)
        return False
    elif isinstance(obj[field_name], list) and len(obj[field_name]) == 0:
        add_error(errs, 10, "Missing Required Fields", "The '%s' field is an empty array." % field_name, dataset_name)
        return False
    return True

def check_string_field(obj, field_name, min_length, dataset_name, errs):
    # checks that a required field exists, is typed as a string, and has a minimum length
    if not check_required_field(obj, field_name, (str, unicode), dataset_name, errs):
        return False
    elif len(obj[field_name].strip()) == 0:
        add_error(errs, 10, "Missing Required Fields", "The '%s' field is present but empty." % field_name, dataset_name)
        return False
    elif len(obj[field_name].strip()) <= min_length:
        add_error(errs, 100, "Are These Okay?", "The '%s' field is very short: \"%s\"" % (field_name, obj[field_name]), dataset_name)
        return False
    return True
    
def check_date_field(obj, field_name, dataset_name, errs):
    # checks that a required date field exists and looks like a date
    if not check_required_field(obj, field_name, (str, unicode), dataset_name, errs):
        return False
    elif len(obj[field_name].strip()) == 0:
        add_error(errs, 10, "Missing Required Fields", "The '%s' field is present but empty." % field_name, dataset_name)
        return False
    else:
        if not ISO8601_REGEX.match(obj[field_name]):
            add_error(errs, 5, "Invalid Required Field Value", "The '%s' field has an invalid ISO 8601 date or date-time value: \"%s\"." % (field_name, obj[field_name]), dataset_name)
            return False
    return True
    
def check_url_field(required, obj, field_name, dataset_name, errs):
    # checks that a required or optional field, if specified, looks like a URL
    if not required and (field_name not in obj or obj[field_name] is None): return True # not required, so OK
    if not check_required_field(obj, field_name, (str, unicode), dataset_name, errs): return False # just checking data type
    if not URL_REGEX.match(obj[field_name]):
        add_error(errs, 5, "Invalid Required Field Value", "The '%s' field has an invalid URL: \"%s\"." % (field_name, obj[field_name]), dataset_name)
        return False
    return True


