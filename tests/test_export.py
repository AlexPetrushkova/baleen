# tests.test_export
# Test the export module - to generate a corpus for machine learning.
#
# Author:   Benjamin Bengfort <benjamin@bengfort.com>
# Created:  Sun Feb 21 15:49:18 2016 -0500
#
# Copyright (C) 2016 Bengfort.com
# For license information, see LICENSE.txt
#
# ID: test_export.py [2988c53] benjamin@bengfort.com $

"""
Test the export module - to generate a corpus for machine learning.
"""

##########################################################################
## Imports
##########################################################################

import unittest
import logging

from mongomock import MongoClient as MockMongoClient
from unittest import mock
from unittest.mock import MagicMock

from baleen.export import *
from baleen.feed import *
from baleen.models import connect
from baleen.exceptions import ExportError

##########################################################################
## Fixtures
##########################################################################

BOOKS_FEED = Feed(
    title = 'The Rumpus.net',
    link = 'http://therumpus.net/feed/',
    urls = {'htmlurl': 'http://therumpus.net'},
    category = 'books',
)
BOOKS_POST = Post(
    feed=BOOKS_FEED,
    title="My Awesome Post",
    content="books",
    url="http://example.com/books.html",
)

POLITICS_FEED = Feed(
    title = 'The Politics Site',
    link = 'http://politicsrock.net/feed/',
    urls = {'htmlurl': 'http://politicsrock.net'},
    category = 'politics',
)
POLITICS_POST = Post(
    feed=POLITICS_FEED,
    title="My Awesome Political Post",
    content="political parties",
    url="http://example.com/politics.html",
)

FOOD_FEED = Feed(
    title = 'I love food',
    link = 'http://foodisthebest.com/atom',
    urls = {'htmlurl': 'http://foodisthebest.com'},
    category = 'food',
)
FOOD_POST = Post(
    feed=FOOD_FEED,
    title="Hamburgers are Good",
    content="ground meat",
    url="http://example.com/mmmmm.html",
)

CATEGORIES_IN_DB = [
    BOOKS_FEED.category,
    POLITICS_FEED.category,
    FOOD_FEED.category,
]

##########################################################################
## Export Tests
##########################################################################

class ExportTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create the mongomock connection
        """
        cls.conn = connect(host='mongomock://localhost')
        assert isinstance(cls.conn, MockMongoClient)

        # Clear out the database
        for feed in Feed.objects(): feed.delete()
        for post in Post.objects(): post.delete()
        assert Feed.objects.count() == 0
        assert Post.objects.count() == 0

        # Set up test feeds
        FeedSync(BOOKS_FEED).sync()
        BOOKS_POST.save()
        FeedSync(FOOD_FEED).sync()
        FOOD_POST.save()
        FeedSync(POLITICS_FEED).sync()
        POLITICS_POST.save()

        assert Feed.objects.count() == 3
        assert Post.objects.count() == 3

    @classmethod
    def tearDownClass(self):
        """
        Drop the mongomock connection
        """
        assert isinstance(self.conn, MockMongoClient)
        self.conn = None

    def test_scheme_specification(self):
        """
        Assert that only known schemes are allowed
        """

        # Make sure good schemes don't error
        for scheme in SCHEMES:
            try:
                exporter = MongoExporter("/tmp/corpus", scheme=scheme)
            except ExportError:
                self.fail("Could not use expected scheme, {}".format(scheme))

        # Make sure bad schemes do error
        for scheme in ('bson', 'xml', 'yaml', 'foo', 'bar'):
            with self.assertRaises(ExportError):
                exporter = MongoExporter("/tmp/corpus", scheme=scheme)

    def test_categories_default(self):
        """
        Assert that categories are set to default when not provided
        """

        exporter = MongoExporter("/tmp/corpus")
        self.assertCountEqual(CATEGORIES_IN_DB, exporter.categories)

    def test_categories_provided(self):
        """
        Assert that provided categories are returned
        """
        categories = ["TestCategory", "Another Category", "Unicode ĆăƮĖƓƠŕƔ"]
        exporter = MongoExporter("/tmp/corpus", categories=categories)
        self.assertCountEqual(categories, exporter.categories)

    def test_feeds_for_list_of_categories(self):
        """
        Assert that getting feeds for a list of categories works
        """
        exporter = MongoExporter("/tmp/corpus", categories=CATEGORIES_IN_DB)
        expected_feeds = [POLITICS_FEED, FOOD_FEED]
        test_categories = ["politics", "food"]
        self.assertCountEqual(expected_feeds , exporter.feeds(categories=test_categories))

    def test_feeds_for_category_string(self):
        """
        Assert that getting feeds for a category as a string
        """
        exporter = MongoExporter("/tmp/corpus", categories=CATEGORIES_IN_DB)
        self.assertCountEqual([POLITICS_FEED], exporter.feeds(categories="politics"))

    def test_feeds_for_all_categories(self):
        """
        Assert that getting feeds with a category returns for all categories
        """
        exporter = MongoExporter("/tmp/corpus", categories=CATEGORIES_IN_DB)
        self.assertCountEqual([POLITICS_FEED, FOOD_FEED, BOOKS_FEED], exporter.feeds())

    def test_writing_readme(self):
        """
        Assert that a readme file is written correctly
        """
        exporter = MongoExporter("/tmp/corpus", categories=CATEGORIES_IN_DB)
        exporter.state = State.Finished
        exporter.readme("/tmp/readme")

        # TODO Assert appropriate readme file

    def test_writing_readme_fails(self):
        """
        Assert writing readme file fails when in an incorrect state
        """
        exporter = MongoExporter("/tmp/corpus", categories=CATEGORIES_IN_DB)
        with self.assertRaises(ExportError):
            exporter.readme("/tmp/readme")

    def test_generating_posts_fails(self):
        """
        Assert generating posts fails when in an incorrect state
        """
        exporter = MongoExporter("/tmp/corpus", categories=CATEGORIES_IN_DB)
        exporter.state = "Some crazy thing"
        with self.assertRaises(ExportError):
            for post, category in exporter.posts():
                self.fail("Should never get to the point where we touch posts")

    """
    MockMongoClient doesn't have a rewind method:
    https://github.com/vmalloc/mongomock/blob/develop/mongomock/collection.py#L1498

    This forces us to mock the post() method here.
    """
    def test_export(self):
        """
        Assert that we can export posts
        """
        exporter = MongoExporter("/tmp/corpus", categories=CATEGORIES_IN_DB)

        # Mock Mongo calls that aren't supported in MockMongoClient
        post_categories = [
            (BOOKS_POST, BOOKS_FEED.category),
            (FOOD_POST, FOOD_FEED.category),
            (POLITICS_POST, POLITICS_FEED.category),
        ]
        exporter.posts = MagicMock(return_value=post_categories)
        exporter.export()

    def test_export_with_root_path_failure(self):
        """
        Assert that root path failures are raised
        """
        root_path = "/tmp/corpus"
        exporter = MongoExporter(root_path, categories=CATEGORIES_IN_DB)
        os.path.exists = lambda path: False if path == root_path else True
        os.mkdir = lambda success: True # Mock directory creation
        os.path.isdir = lambda path: False if path == root_path else True

        with self.assertRaises(ExportError):
            exporter.export()

    def test_export_with_category_path_failure(self):
        """
        Assert that category path failures are raised
        """
        root_path = "/tmp/corpus"
        exporter = MongoExporter(root_path, categories=CATEGORIES_IN_DB)
        for category in CATEGORIES_IN_DB:
            category_path = os.path.join(root_path, category)
            os.path.exists = lambda path: False if path == category_path else True
            os.mkdir = lambda success: True # Mock directory creation
            os.path.isdir = lambda path: False if path == category_path else True

            with self.assertRaises(ExportError):
                exporter.export()


class SanitizeHtmlTests(unittest.TestCase):
    """ Tests the exporter's HTML sanitize methods """

    @classmethod
    def setUpClass(cls):
        cls.sample_html = ('<html>'
                           '<head><script>javascript here</script></head>'
                           '<body><b>body &amp;\n mind</b></body>'
                           '</html>')

        cls.conn = connect(host='mongomock://localhost')
        assert isinstance(cls.conn, MockMongoClient)
        root_path = '/tmp/corpus'
        cls.exporter = MongoExporter(root_path, categories=CATEGORIES_IN_DB)

    @classmethod
    def tearDownClass(self):
        """
        Drop the mongomock connection
        """
        assert isinstance(self.conn, MockMongoClient)
        self.conn = None

    def test_sanitize_requires_a_valid_level(self):
        """  Sanitize_html requires a supported level """
        with self.assertRaises(ExportError):
            self.exporter.sanitize_html(self.sample_html, "bogus")

    def test_sanitize_returns_input_for_level_none(self):
        """  sanitize_html returns unmodified input for level None """
        self.assertEqual(self.exporter.sanitize_html(self.sample_html, None), self.sample_html)

    def test_sanitize_raw(self):
        """  Sanitize level raw returns the content as submitted """
        self.assertEqual(self.exporter.sanitize_html(self.sample_html, RAW), self.sample_html)

    def test_sanitize_safe(self):
        """  Sanitize level safe applies Readability and returns the body """

        # Give Readability a simpler HTML sample to keep its parse strategy simple
        sample_html = ('<html>'
                       '<head><script>javascript here</script></head>'
                       '<body>body</body>'
                       '</html>')
        expected = '<body id="readabilityBody">body</body>'
        self.assertEqual(self.exporter.sanitize_html(sample_html, SAFE), expected)

    def test_sanitize_text(self):
        """
        Sanitize level text strips HTML tags, removes newlines,
         and converts the html entity ampersand into an ampersand character
        """
        expected = 'body & mind'
        self.assertEqual(self.exporter.sanitize_html(self.sample_html, TEXT), expected)
