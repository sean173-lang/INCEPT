"""Offline PDF/structured ingestion; real demo amounts manually checked on pp.6–8."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from decimal import Decimal
from unittest.mock import patch
from offline_support import OfflineTestCase
from scripts.german_accounts import ingest,report,german_number,pdf_pages

MANIFEST=Path(__file__).resolve().parents[1]/'references/german_accounts_sigma_2024.json'


class GermanAccountsTests(OfflineTestCase):
    def setUp(self):self.statement=json.loads(MANIFEST.read_text())

    def test_checked_actual_figures_and_mixed_units(self):
        data=ingest(self.statement);markdown,a=report(data)
        self.assertEqual(a['periods'][1]['facts']['revenue']['value'],'3450128.25')
        expected={'net_income':'130888.28','total_assets':'1559700.19','equity':'899199.62','cash':'135303.51'}
        for metric,value in expected.items():self.assertEqual(a['periods'][1]['facts'][metric]['value'],value)
        self.assertEqual(a['periods'][0]['normalized_values']['revenue']['value'],'2578000')
        self.assertEqual(a['comparisons'][0]['changes']['cash']['absolute_change'],'-138696.49')
        self.assertEqual(a['comparisons'][0]['changes']['revenue']['absolute_change'],'872128.25')
        self.assertAlmostEqual(float(a['periods'][1]['ratios']['equity_ratio']['value']),0.5765208119901556)
        self.assertAlmostEqual(float(a['periods'][1]['ratios']['net_margin']['value']),0.03793722160908076)
        self.assertIsNone(a['periods'][1]['ratios']['current_ratio']['value'])
        self.assertIn('NOT Shapesty',markdown);self.assertIn('PDF page 6',markdown)
        self.assertIn('50.',str(-Decimal(a['comparisons'][0]['changes']['cash']['percent_change'])))
        self.assertIn('Equity ratio decreased',markdown);self.assertIn('rounded',markdown)

    def test_decimal_formats_and_absence(self):
        self.assertEqual(german_number('(1.234,56)'),'-1234.56')
        self.assertEqual(german_number('0,00'),'0.00')
        for value in ('-', '',None,'1,234.56','1.23',True):
            with self.assertRaises(ValueError):german_number(value)

    def test_missing_revenue_not_zero_and_units_not_inferred(self):
        s=self.statement
        for p in s['periods']:
            p['facts'].pop('revenue')
            p['facts']['equity']['unit']['currency']=None
        _,a=report(ingest(s))
        self.assertIsNone(a['periods'][0]['facts']['revenue']['value'])
        self.assertIsNone(a['periods'][0]['ratios']['net_margin']['value'])
        self.assertIsNone(a['periods'][0]['ratios']['equity_ratio']['value'])

    def test_zero_negative_and_incompatible_periods(self):
        s=self.statement;s['periods'][1]['facts']['net_income'].update(raw_value='-100,00',quote='loss -100,00')
        s['periods'][0]['facts']['revenue'].update(raw_value='0',quote='revenue 0')
        _,a=report(ingest(s));self.assertIsNone(a['periods'][0]['ratios']['net_margin']['value'])
        self.assertTrue(any(i['description']=='Reported net loss' for i in a['indicators']))
        s['periods'][1]['scope']='consolidated'
        _,a=report(ingest(s));self.assertIsNone(a['comparisons'][0]['changes']['cash']['absolute_change'])

    def test_required_provenance_and_review(self):
        for mutate in (lambda s:s.update(reviewed=False),lambda s:s['source'].update(sha256='fake'),
                       lambda s:s['periods'][0]['facts']['cash'].update(quote='amount missing'),
                       lambda s:s['periods'][0]['facts']['cash'].update(page=0)):
            s=copy.deepcopy(self.statement);mutate(s)
            with self.assertRaises(ValueError):ingest(s)

    def test_pdf_hash_and_ambiguous_matches_fail_closed(self):
        pages=['dummy']*9
        pages[8]=self.statement['context']['quote']
        with patch('scripts.german_accounts.pdf_pages',return_value=(pages,'0'*64)):
            with self.assertRaisesRegex(ValueError,'hash'):ingest(self.statement,pdf='unused.pdf')
        s=self.statement;rule=s['periods'][0]['facts']['revenue'];rule['unit']['pattern']='header'
        pages[7]='header\n1. Umsatzerlöse 1.000,00 1.000\n1. Umsatzerlöse 2.000,00 2.000'
        s['periods'][0]['facts']={'revenue':rule};s['periods']=s['periods'][:1]
        with patch('scripts.german_accounts.pdf_pages',return_value=(pages,s['source']['sha256'])):
            with self.assertRaisesRegex(ValueError,'Ambiguous'):ingest(s,pdf='unused.pdf')

    def test_actual_unrestricted_pdf_round_trip(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 750 Td (Calendar year) Tj 0 -30 Td (2024 EUR 2023 TEUR) Tj 0 -30 Td (Revenue 2.000,00 1) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(stream)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.pdf'
            with path.open('wb') as f:writer.write(f)
            s=copy.deepcopy(self.statement);s['source']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            s['context']={'page':1,'quote':'Calendar year'}
            s['periods']=s['periods'][1:]
            s['periods'][0]['facts']={'revenue':{'page':1,'pattern':r'Revenue (?P<current>[\d.,]+) (?P<previous>[\d.,]+)','column':'current',
                'unit':{'page':1,'quote':'2024 EUR','pattern':'2024 EUR 2023 TEUR','currency':'EUR','scale':1}}}
            result=ingest(s,pdf=path)
            self.assertEqual(result['periods'][0]['facts']['revenue']['value'],'2000.00')
            self.assertEqual(result['periods'][0]['facts']['revenue']['source_sha256'],s['source']['sha256'])
            writer.encrypt('private-password')
            with path.open('wb') as f:writer.write(f)
            with self.assertRaises(Exception):pdf_pages(path)

    def test_no_signed_urls_in_report(self):
        self.statement['source']['url']+='?signature=PRIVATE&token=HIDDEN'
        result,_=report(ingest(self.statement))
        self.assertNotIn('PRIVATE',result);self.assertNotIn('HIDDEN',result)
