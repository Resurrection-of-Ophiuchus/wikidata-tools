import pywikibot
import csv

# Property values from live wikidata:
p_abundance = 'P2374'  # (natural abundance)
p_stated_in = 'P248'
p_ref_url = 'P854'
p_retrieved = 'P813'
p_edition = 'P393'
nudat_qid = 'Q21234191'
p_uncertainty_corr = 'P2571'
standard_dev_qid = 'Q159375'

retrieval_date = pywikibot.WbTime(year=2016, month=6, day=23)

precision = 10 ** -10

site = pywikibot.Site('wikidata', 'wikidata')
repo = site.data_repository()


def get_item(item_id):
    item = pywikibot.ItemPage(repo, item_id)
    item.get()
    return item


def check_claim_and_uncert(item, check_property, data):
    """
    Requires a property, value, uncertainty and returns boolean.
    Returns the claim that fits into the defined precision or None.
    """
    item_dict = item.get()
    value, uncert = data
    value, uncert = float(value), float(uncert)
    try:
        claims = item_dict['claims'][check_property]
    except KeyError:
        return None

    try:
        claim_exists = False
        uncert_set = False
        for claim in claims:
            wb_quant = claim.getTarget()
            delta_amount = float(wb_quant.amount) - value
            if abs(delta_amount) < precision:
                claim_exists = True
            delta_lower = float(wb_quant.amount - wb_quant.lowerBound)
            delta_upper = float(wb_quant.upperBound - wb_quant.amount)
            check_lower = abs(uncert - delta_lower) < precision
            check_upper = abs(delta_upper - uncert) < precision
            if check_upper and check_lower:
                uncert_set = True
# Also should check unit?

            if claim_exists and uncert_set:
                return claim
    except BaseException as e:
        print("exception in checking claim: {}".format(e))
        return None


def check_source_set(claim, source_map):
    source_claims = claim.getSources()
    if len(source_claims) == 0:
        return False

    for source in source_claims:
        all_properties_present = True
        for src_property in source_map.keys():
            target_type, source_value = source_map[src_property]
            try:
                sources_with_property = source[src_property]
            except KeyError:
                continue
            found = False
            if target_type == 'item':
                found = source_value in map(lambda src: src.target.id, sources_with_property)
            elif target_type == 'string':
                found = source_value in map(lambda src: src.target, sources_with_property)
            if not found:
                all_properties_present = False
                break
        if all_properties_present:
            return True
    return False


def add_quantity_claim(item, prop, data):
    value, uncert = data
    value, uncert = float(value), float(uncert)
    claim = pywikibot.Claim(repo, prop)
    wb_quant = pywikibot.WbQuantity(value, error=uncert)
    claim.setTarget(wb_quant)
    item.addClaim(claim, bot=True, summary="Adding natural abundance claim from NNDC.")
    return claim


def add_qualifier(claim, qualifier_property, qualifier_item):
    qualifier = pywikibot.Claim(repo, qualifier_property)
    qualifier.setTarget(qualifier_item)
    claim.addQualifier(qualifier, bot=True)
    return True


def create_source_claim(claim, source_map):
    source_claims = []
    for src_prop in source_map.keys():
        target_type, source_value = source_map[src_prop]
        source_claim = pywikibot.Claim(repo, src_prop, isReference=True)
        if target_type == 'item':
            source_page = pywikibot.ItemPage(repo, source_value)
            source_claim.setTarget(source_page)
        else:
            source_claim.setTarget(source_value)
        source_claims.append(source_claim)
    claim.addSources(source_claims, bot=True)
    return True


def process_nndc_data(filename):
    standard_dev = pywikibot.ItemPage(repo, standard_dev_qid)
    with open(filename) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            nuclide_qid, abundance, uncertainty, nuclide_name, nndc_url = row
            nuclide = get_item(nuclide_qid)
            if uncertainty == 'None':
                uncertainty = 0.0
            hl_claim = check_claim_and_uncert(nuclide, p_abundance, [abundance, uncertainty])
            if hl_claim is None:
                print('New entry: {0}+-{1} for {2} ({3})'.format(
                    abundance, uncertainty, nuclide_qid, nuclide_name))
                new_claim = add_quantity_claim(nuclide, p_abundance, [abundance, uncertainty])
                print('Add uncertainty qualifier')
                add_qualifier(new_claim, p_uncertainty_corr, standard_dev)
                source_map = {p_stated_in: ['item', nudat_qid],
                              p_edition: ['string', '2.6'],
                              p_ref_url: ['string', nndc_url],
                              p_retrieved: ['date', retrieval_date]}
                print('Add source: {0}'.format(nndc_url))
                create_source_claim(new_claim, source_map)
            else:
                source_map = {p_stated_in: ['item', nudat_qid],
                              p_edition: ['string', '2.6'],
                              p_ref_url: ['string', nndc_url]}
                if not check_source_set(hl_claim, source_map):
                    source_map[p_retrieved] = ['date', retrieval_date]
                    create_source_claim(hl_claim, source_map)

process_nndc_data('abundance_data.csv')
