from django.conf import settings
from django.contrib.auth.models import User
from model_mommy import mommy
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from ..test_api import create_default_roles, assign_user_to_role


class TestProjectList(APITestCase):

    @classmethod
    def setUpTestData(cls):
        create_default_roles()
        cls.password = 'pass'
        cls.member = User.objects.create_user(username='member', password=cls.password)
        cls.non_member = User.objects.create_user(username='non-member', password=cls.password)
        cls.project = mommy.make('TextClassificationProject', users=[cls.member])
        cls.url = reverse(viewname='project_list')
        cls.num_project = cls.member.projects.count()

    def test_returns_project_to_member(self):
        self.client.login(username=self.member.username, password=self.password)
        response = self.client.get(self.url)
        projects = response.data
        self.assertEqual(len(projects), self.num_project)
        self.assertEqual(projects[0]['id'], self.project.id)

    def test_does_not_return_project_to_non_member(self):
        self.client.login(username=self.non_member.username, password=self.password)
        response = self.client.get(self.url)
        projects = response.data
        self.assertEqual(len(projects), 0)

    def test_disallows_unauthenticated_user_to_see_project(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestProjectCreate(APITestCase):

    @classmethod
    def setUpTestData(cls):
        create_default_roles()
        cls.password = 'pass'
        cls.user = User.objects.create_user(username='user', password=cls.password)
        cls.url = reverse(viewname='project_list')
        cls.data = {
            'name': 'example',
            'description': 'example',
            'project_type': 'DocumentClassification',
            'resourcetype': 'TextClassificationProject'
        }

    def test_allows_authenticated_user_to_create_project(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(self.url, data=self.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_disallows_unauthenticated_user_to_create_project(self):
        response = self.client.post(self.url, data=self.data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestProjectDetail(APITestCase):

    @classmethod
    def setUpTestData(cls):
        create_default_roles()
        cls.password = 'pass'
        cls.member = User.objects.create_user(username='member', password=cls.password)
        cls.non_member = User.objects.create_user(username='non-member', password=cls.password)
        cls.project = mommy.make('TextClassificationProject', users=[cls.member])
        cls.url = reverse(viewname='project_detail', args=[cls.project.id])

    def test_returns_detail_to_member(self):
        self.client.login(username=self.member.username, password=self.password)
        response = self.client.get(self.url)
        self.assertEqual(response.data['id'], self.project.id)

    def test_does_not_return_detail_to_non_member(self):
        self.client.login(username=self.non_member.username, password=self.password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_does_not_return_detail_to_unauthenticated_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestProjectUpdate(APITestCase):

    @classmethod
    def setUpTestData(cls):
        create_default_roles()
        cls.password = 'pass'
        cls.admin = User.objects.create_user(username='admin', password=cls.password)
        cls.member = User.objects.create_user(username='member', password=cls.password)
        cls.other_project_admin = User.objects.create_user(username='other_admin', password=cls.password)

        cls.project1 = mommy.make('TextClassificationProject', users=[cls.admin, cls.member])
        cls.project2 = mommy.make('TextClassificationProject', users=[cls.other_project_admin])

        assign_user_to_role(cls.member, cls.project1, role_name=settings.ROLE_ANNOTATOR)

        cls.url = reverse(viewname='project_detail', args=[cls.project1.id])
        cls.data = {'name': 'lorem'}

    def test_allows_project_admin_to_update_project(self):
        self.client.login(username=self.admin, password=self.password)
        response = self.client.patch(self.url, data=self.data)
        self.assertEqual(response.data['name'], self.data['name'])

    def test_disallows_non_admin_to_update_project(self):
        self.client.login(username=self.member, password=self.password)
        response = self.client.patch(self.url, data=self.data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_disallows_non_member_to_update_project(self):
        self.client.login(username=self.other_project_admin, password=self.password)
        response = self.client.patch(self.url, data=self.data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestProjectDelete(APITestCase):

    @classmethod
    def setUpTestData(cls):
        create_default_roles()
        cls.password = 'pass'
        cls.admin = User.objects.create_user(username='admin', password=cls.password)
        cls.member = User.objects.create_user(username='member', password=cls.password)
        cls.other_project_admin = User.objects.create_user(username='other_admin', password=cls.password)

        cls.project1 = mommy.make('TextClassificationProject', users=[cls.admin, cls.member])
        cls.project2 = mommy.make('TextClassificationProject', users=[cls.other_project_admin])

        assign_user_to_role(cls.member, cls.project1, role_name=settings.ROLE_ANNOTATOR)

        cls.url = reverse(viewname='project_detail', args=[cls.project1.id])

    def test_allows_project_admin_to_delete_project(self):
        self.client.login(username=self.admin, password=self.password)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_disallows_non_admin_to_delete_project(self):
        self.client.login(username=self.member, password=self.password)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_disallows_non_member_to_delete_project(self):
        self.client.login(username=self.other_project_admin, password=self.password)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
