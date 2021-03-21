import os

from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from model_mommy import mommy
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from ...exceptions import FileParseException
from ...models import DOCUMENT_CLASSIFICATION, SEQUENCE_LABELING, SEQ2SEQ, SPEECH2TEXT
from ..test_api import create_default_roles, assign_user_to_role, DATA_DIR, remove_all_role_mappings
from ...utils import CoNLLParser, PlainTextParser, CSVParser, JSONParser, FastTextParser


class TestUploader(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.super_user_name = 'super_user_name'
        cls.super_user_pass = 'super_user_pass'
        # Todo: change super_user to project_admin.
        create_default_roles()
        super_user = User.objects.create_superuser(username=cls.super_user_name,
                                                   password=cls.super_user_pass,
                                                   email='fizz@buzz.com')
        cls.classification_project = mommy.make('TextClassificationProject',
                                                users=[super_user], project_type=DOCUMENT_CLASSIFICATION)
        cls.labeling_project = mommy.make('SequenceLabelingProject',
                                          users=[super_user], project_type=SEQUENCE_LABELING)
        cls.seq2seq_project = mommy.make('Seq2seqProject', users=[super_user], project_type=SEQ2SEQ)
        assign_user_to_role(project_member=super_user, project=cls.classification_project,
                            role_name=settings.ROLE_PROJECT_ADMIN)
        assign_user_to_role(project_member=super_user, project=cls.labeling_project,
                            role_name=settings.ROLE_PROJECT_ADMIN)
        assign_user_to_role(project_member=super_user, project=cls.seq2seq_project,
                            role_name=settings.ROLE_PROJECT_ADMIN)

    def setUp(self):
        self.client.login(username=self.super_user_name,
                          password=self.super_user_pass)

    def upload_test_helper(self, project_id, filename, file_format, expected_status, **kwargs):
        url = reverse(viewname='doc_uploader', args=[project_id])

        with open(os.path.join(DATA_DIR, filename), 'rb') as f:
            response = self.client.post(url, data={'file': f, 'format': file_format})

        self.assertEqual(response.status_code, expected_status)

    def label_test_helper(self, project_id, expected_labels, expected_label_keys):
        url = reverse(viewname='label_list', args=[project_id])
        expected_keys = {key for label in expected_labels for key in label}

        response = self.client.get(url).json()

        actual_labels = [{key: value for (key, value) in label.items() if key in expected_keys}
                         for label in response]

        self.assertCountEqual(actual_labels, expected_labels)

        for label in response:
            for expected_label_key in expected_label_keys:
                self.assertIsNotNone(label.get(expected_label_key))

    def test_can_upload_conll_format_file(self):
        self.upload_test_helper(project_id=self.labeling_project.id,
                                filename='labeling.conll',
                                file_format='conll',
                                expected_status=status.HTTP_201_CREATED)

    def test_cannot_upload_wrong_conll_format_file(self):
        self.upload_test_helper(project_id=self.labeling_project.id,
                                filename='labeling.invalid.conll',
                                file_format='conll',
                                expected_status=status.HTTP_400_BAD_REQUEST)

    def test_can_upload_classification_csv(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.csv',
                                file_format='csv',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_classification_csv_with_out_of_order_columns(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example_out_of_order_columns.csv',
                                file_format='csv',
                                expected_status=status.HTTP_201_CREATED)

        self.label_test_helper(
            project_id=self.classification_project.id,
            expected_labels=[
                {'text': 'Positive'},
                {'text': 'Negative'},
            ],
            expected_label_keys=[],
        )

    def test_can_upload_csv_with_non_utf8_encoding(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.utf16.csv',
                                file_format='csv',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_seq2seq_csv(self):
        self.upload_test_helper(project_id=self.seq2seq_project.id,
                                filename='example.csv',
                                file_format='csv',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_single_column_csv(self):
        self.upload_test_helper(project_id=self.seq2seq_project.id,
                                filename='example_one_column.csv',
                                file_format='csv',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_csv_file_does_not_match_column_and_row(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example_column_and_row_not_matching.csv',
                                file_format='csv',
                                expected_status=status.HTTP_201_CREATED)

    def test_cannot_upload_csv_file_has_too_many_columns(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.invalid.2.csv',
                                file_format='csv',
                                expected_status=status.HTTP_400_BAD_REQUEST)

    def test_can_upload_classification_excel(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.xlsx',
                                file_format='excel',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_seq2seq_excel(self):
        self.upload_test_helper(project_id=self.seq2seq_project.id,
                                filename='example.xlsx',
                                file_format='excel',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_single_column_excel(self):
        self.upload_test_helper(project_id=self.seq2seq_project.id,
                                filename='example_one_column.xlsx',
                                file_format='excel',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_excel_file_does_not_match_column_and_row(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example_column_and_row_not_matching.xlsx',
                                file_format='excel',
                                expected_status=status.HTTP_201_CREATED)

    def test_cannot_upload_excel_file_has_too_many_columns(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.invalid.2.xlsx',
                                file_format='excel',
                                expected_status=status.HTTP_400_BAD_REQUEST)

    @override_settings(IMPORT_BATCH_SIZE=1)
    def test_can_upload_small_batch_size(self):
        self.upload_test_helper(project_id=self.seq2seq_project.id,
                                filename='example_one_column_no_header.xlsx',
                                file_format='excel',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_classification_jsonl(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='classification.jsonl',
                                file_format='json',
                                expected_status=status.HTTP_201_CREATED)

        self.label_test_helper(
            project_id=self.classification_project.id,
            expected_labels=[
                {'text': 'positive', 'suffix_key': 'p', 'prefix_key': None},
                {'text': 'negative', 'suffix_key': 'n', 'prefix_key': None},
                {'text': 'neutral', 'suffix_key': 'n', 'prefix_key': 'ctrl'},
            ],
            expected_label_keys=[
                'background_color',
                'text_color',
            ])

    def test_can_upload_labeling_jsonl(self):
        self.upload_test_helper(project_id=self.labeling_project.id,
                                filename='labeling.jsonl',
                                file_format='json',
                                expected_status=status.HTTP_201_CREATED)

        self.label_test_helper(
            project_id=self.labeling_project.id,
            expected_labels=[
                {'text': 'LOC', 'suffix_key': 'l', 'prefix_key': None},
                {'text': 'ORG', 'suffix_key': 'o', 'prefix_key': None},
                {'text': 'PER', 'suffix_key': 'p', 'prefix_key': None},
            ],
            expected_label_keys=[
                'background_color',
                'text_color',
            ])

    def test_can_upload_seq2seq_jsonl(self):
        self.upload_test_helper(project_id=self.seq2seq_project.id,
                                filename='seq2seq.jsonl',
                                file_format='json',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_plain_text(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.txt',
                                file_format='plain',
                                expected_status=status.HTTP_201_CREATED)

    def test_can_upload_data_without_label(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.jsonl',
                                file_format='json',
                                expected_status=status.HTTP_201_CREATED)

    @classmethod
    def doCleanups(cls):
        remove_all_role_mappings()


@override_settings(CLOUD_BROWSER_APACHE_LIBCLOUD_PROVIDER='LOCAL')
@override_settings(CLOUD_BROWSER_APACHE_LIBCLOUD_ACCOUNT=os.path.dirname(DATA_DIR))
@override_settings(CLOUD_BROWSER_APACHE_LIBCLOUD_SECRET_KEY='not-used')
class TestCloudUploader(TestUploader):
    def upload_test_helper(self, project_id, filename, file_format, expected_status, **kwargs):
        query_params = {
            'project_id': project_id,
            'upload_format': file_format,
            'container': kwargs.pop('container', os.path.basename(DATA_DIR)),
            'object': filename,
        }

        query_params.update(kwargs)

        response = self.client.get(reverse('cloud_uploader'), query_params)

        self.assertEqual(response.status_code, expected_status)

    def test_cannot_upload_with_missing_file(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='does-not-exist',
                                file_format='json',
                                expected_status=status.HTTP_400_BAD_REQUEST)

    def test_cannot_upload_with_missing_container(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.jsonl',
                                container='does-not-exist',
                                file_format='json',
                                expected_status=status.HTTP_400_BAD_REQUEST)

    def test_cannot_upload_with_missing_query_parameters(self):
        response = self.client.get(reverse('cloud_uploader'), {'project_id': self.classification_project.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_upload_with_redirect(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.jsonl',
                                next='http://somewhere',
                                file_format='json',
                                expected_status=status.HTTP_302_FOUND)

    def test_can_upload_with_redirect_to_blank(self):
        self.upload_test_helper(project_id=self.classification_project.id,
                                filename='example.jsonl',
                                next='about:blank',
                                file_format='json',
                                expected_status=status.HTTP_201_CREATED)


class TestFeatures(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_name = 'user_name'
        cls.user_pass = 'user_pass'
        create_default_roles()
        cls.user = User.objects.create_user(username=cls.user_name, password=cls.user_pass, email='fizz@buzz.com')

    def setUp(self):
        self.client.login(username=self.user_name, password=self.user_pass)

    @override_settings(CLOUD_BROWSER_APACHE_LIBCLOUD_PROVIDER=None)
    def test_no_cloud_upload(self):
        response = self.client.get(reverse('features'))

        self.assertFalse(response.json().get('cloud_upload'))


@override_settings(IMPORT_BATCH_SIZE=2)
class TestParser(APITestCase):

    def parser_helper(self, filename, parser, include_label=True):
        with open(os.path.join(DATA_DIR, filename), mode='rb') as f:
            result = list(parser.parse(f))
            for data in result:
                for r in data:
                    self.assertIn('text', r)
                    if include_label:
                        self.assertIn('labels', r)
        return result

    def test_give_valid_data_to_conll_parser(self):
        self.parser_helper(filename='labeling.conll', parser=CoNLLParser())

    def test_give_valid_data_to_conll_parser_with_trailing_newlines(self):
        result = self.parser_helper(filename='labeling.trailing.conll', parser=CoNLLParser())
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 1)

    def test_plain_parser(self):
        self.parser_helper(filename='example.txt', parser=PlainTextParser(), include_label=False)

    def test_give_invalid_data_to_conll_parser(self):
        with self.assertRaises(FileParseException):
            self.parser_helper(filename='labeling.invalid.conll',
                               parser=CoNLLParser())

    def test_give_classification_data_to_csv_parser(self):
        self.parser_helper(filename='example.csv', parser=CSVParser(), include_label=False)

    def test_give_seq2seq_data_to_csv_parser(self):
        self.parser_helper(filename='example.csv', parser=CSVParser(), include_label=False)

    def test_give_classification_data_to_json_parser(self):
        self.parser_helper(filename='classification.jsonl', parser=JSONParser())

    def test_give_labeling_data_to_json_parser(self):
        self.parser_helper(filename='labeling.jsonl', parser=JSONParser())

    def test_give_seq2seq_data_to_json_parser(self):
        self.parser_helper(filename='seq2seq.jsonl', parser=JSONParser())

    def test_give_data_without_label_to_json_parser(self):
        self.parser_helper(filename='example.jsonl', parser=JSONParser(), include_label=False)

    def test_give_labeling_data_to_fasttext_parser(self):
        self.parser_helper(filename='example_fasttext.txt', parser=FastTextParser())

    def test_give_data_without_label_name_to_fasttext_parser(self):
        with self.assertRaises(FileParseException):
            self.parser_helper(filename='example_fasttext_label_tag_without_name.txt', parser=FastTextParser())

    def test_give_data_without_text_to_fasttext_parser(self):
        with self.assertRaises(FileParseException):
            self.parser_helper(filename='example_fasttext_without_text.txt', parser=FastTextParser())


class TestDownloader(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.super_user_name = 'super_user_name'
        cls.super_user_pass = 'super_user_pass'
        # Todo: change super_user to project_admin.
        create_default_roles()
        super_user = User.objects.create_superuser(username=cls.super_user_name,
                                                   password=cls.super_user_pass,
                                                   email='fizz@buzz.com')
        cls.classification_project = mommy.make('TextClassificationProject',
                                                users=[super_user], project_type=DOCUMENT_CLASSIFICATION)
        cls.labeling_project = mommy.make('SequenceLabelingProject',
                                          users=[super_user], project_type=SEQUENCE_LABELING)
        cls.seq2seq_project = mommy.make('Seq2seqProject', users=[super_user], project_type=SEQ2SEQ)
        cls.speech2text_project = mommy.make('Speech2textProject', users=[super_user], project_type=SPEECH2TEXT)
        cls.classification_url = reverse(viewname='doc_downloader', args=[cls.classification_project.id])
        cls.labeling_url = reverse(viewname='doc_downloader', args=[cls.labeling_project.id])
        cls.seq2seq_url = reverse(viewname='doc_downloader', args=[cls.seq2seq_project.id])
        cls.speech2text_url = reverse(viewname='doc_downloader', args=[cls.speech2text_project.id])

    def setUp(self):
        self.client.login(username=self.super_user_name,
                          password=self.super_user_pass)

    def download_test_helper(self, url, format, expected_status):
        response = self.client.get(url, data={'q': format})
        self.assertEqual(response.status_code, expected_status)

    def test_cannot_download_conll_format_file(self):
        self.download_test_helper(url=self.labeling_url,
                                  format='conll',
                                  expected_status=status.HTTP_400_BAD_REQUEST)

    def test_can_download_classification_csv(self):
        self.download_test_helper(url=self.classification_url,
                                  format='csv',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_labeling_csv(self):
        self.download_test_helper(url=self.labeling_url,
                                  format='csv',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_seq2seq_csv(self):
        self.download_test_helper(url=self.seq2seq_url,
                                  format='csv',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_classification_jsonl(self):
        self.download_test_helper(url=self.classification_url,
                                  format='json',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_labeling_jsonl(self):
        self.download_test_helper(url=self.labeling_url,
                                  format='json',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_seq2seq_jsonl(self):
        self.download_test_helper(url=self.seq2seq_url,
                                  format='json',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_speech2text_jsonl(self):
        self.download_test_helper(url=self.speech2text_url,
                                  format='json',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_labelling_jsonl(self):
        self.download_test_helper(url=self.labeling_url,
                                  format='jsonl',
                                  expected_status=status.HTTP_200_OK)

    def test_can_download_plain_text(self):
        self.download_test_helper(url=self.classification_url,
                                  format='plain',
                                  expected_status=status.HTTP_400_BAD_REQUEST)

    def test_can_download_classification_fasttext(self):
        self.download_test_helper(url=self.classification_url,
                                  format='txt',
                                  expected_status=status.HTTP_200_OK)
