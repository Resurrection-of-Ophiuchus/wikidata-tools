import json
import csv
from wikidataintegrator import wdi_core

class RorData:
    def __init__(self, ror_data_filename, wikidata_ror_filename):
        self.ror_lookup_hash = {}
        with open(ror_data_filename) as ror_file:
            self.ror_full_data = json.load(ror_file)
            for inst in self.ror_full_data:
                ror_id = inst['id'].split('/')[-1]
                self.ror_lookup_hash[ror_id] = inst
        self.fetch_wikidata_relations(wikidata_ror_filename)

    def fetch_wikidata_relations(self, wikidata_ror_filename):
        self.ror_wikidata_links = {}
        with open(wikidata_ror_filename) as wd_ror:
            reader = csv.reader(wd_ror)
            for row in reader:
                wikidata_id = row[0]
                ror_id = row[1]
                self.ror_wikidata_links[ror_id] = wikidata_id

    def verify_not_in_wikidata(self, ror_id):
        results = wdi_core.WDItemEngine.execute_sparql_query(
                query="SELECT ?item ?ror WHERE {{ ?item wdt:P6782 '{0}' . }}".format(ror_id))
        return len(results['results']['bindings']) == 0

    def load_country_map(self, country_map_file):
        self.country_map = {}
        with open(country_map_file) as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                country, country_qid = row
                self.country_map[country] = country_qid

    def load_type_map(self, type_map_file):
        self.org_types_map = {}
        with open(type_map_file) as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                type, type_qid = row
                self.org_types_map[type] = type_qid

    def all_valid_ids(self):
        valid_id_list = []
        for inst in self.ror_full_data:
            if inst['status'] == 'active':
                valid_id_list.append(inst['id'].split('/')[-1])
        return valid_id_list

    def valid_ids_not_in_wikidata(self):
        id_list = []
        for ror_id in self.all_valid_ids():
            if ror_id not in self.ror_wikidata_links:
                id_list.append(ror_id)
        return id_list

    def base_data_for_id(self, ror_id):
        org = self.ror_lookup_hash[ror_id]
        org_name = None
        for name in org['names']:
            if 'ror_display' in name['types']:
                org_name = name['value']
        org_inception = org['established']
        website = None
        city = None
        country = None
        org_country_qid = None
        org_type_label = 'other' # default
        if org['types']:
            for type_label in org['types']:
                if type_label != 'funder':
                    org_type_label = type_label
        org_type_qid = self.org_types_map[org_type_label]
        if org['links']:
            for link_entry in org['links']:
                if link_entry['type'] == 'website':
                    website = link_entry['value'].strip() # remove any extraneous spaces
        if org['locations']:
            org_location = org['locations'][0]
            city_entry = org_location['geonames_details']
            city = city_entry['name']
            country = city_entry['country_name']
            ccode = city_entry['country_code']
            org_country_qid = self.country_map[ccode]
        org_desc_list = []
        if org_type_label != 'other':
            org_desc_list.append(org_type_label.lower())
        if (org_type_label != 'company') and (org_type_label != 'facility'):
            org_desc_list.append('organization')
        org_desc_list.append('in')
        if city:
            org_desc_list.append(city + ',')
        org_desc_list.append(country)
        org_description = ' '.join(org_desc_list)
        return {
            'ror_id': ror_id,
            'label': org_name,
            'description': org_description,
            'inception': org_inception,
            'type_qid': org_type_qid,
            'website': website,
            'country_qid': org_country_qid
        }

    def aliases_for_id(self, ror_id):
        org = self.ror_lookup_hash[ror_id]
        org_aliases = {}
        for name_hash in org['names']:
            if 'ror_display' in name_hash['types']:
                continue
            if 'label' in name_hash['types']:
                continue
            language = name_hash['lang']
            if not language:
                language = 'en'
            if language not in org_aliases:
                org_aliases[language] = []
            org_aliases[language].append(name_hash['value'])
        return org_aliases

    def labels_for_id(self, ror_id):
        org = self.ror_lookup_hash[ror_id]
        org_labels = []
        for name_hash in org['names']:
            if 'ror_display' in name_hash['types']:
                continue
            if 'label' in name_hash['types']:
                language = name_hash['lang']
                label = name_hash['value']
                org_labels.append({'label':label,'language':language})
        return org_labels
