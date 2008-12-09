#!/usr/bin/python
"""Script to generate a WordPress eXtended RSS (WXR) file from a mephisto
database.
"""

# Copyright 2008 David Murphy <schwuk@schwuk.com>.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import MySQLdb
import re
import sys
import xml.dom.minidom

from datetime import datetime
from optparse import OptionParser

class Export(object):
    """Handles the details of creating a WordPress eXtended RSS (WXR)."""
    
    def __init__(self, connection):
        """Creates the basic document."""
        self.connection = connection
        self.site = ''

        self.xml = xml.dom.minidom.Document()
        self.rss = self._create_element('rss', self.xml)
        self.rss.setAttribute('xmlns:content',
                              'http://purl.org/rss/1.0/modules/content/')
        self.rss.setAttribute('xmlns:wfw',
                              'http://wellformedweb.org/CommentAPI/')
        self.rss.setAttribute('xmlns:dc', 'http://purl.org/dc/elements/1.1/')
        self.rss.setAttribute('xmlns:wp', 'http://wordpress.org/export/1.0/')
        self.channel = self._create_element('channel', self.rss)
    
    def _create_element(self, name, parent=None, value=None):
        """Helper function for creating XML elements.
        
        Parameters:
        :param name: The name of the element
        :type name: ``str``
        :param parent: (Optional) The XML node you want this element to be a
        child of.
        :type b: ``Node``
    
        :return: The element
        :rtype: ``Node``.        
        """
        element = self.xml.createElement(str(name))
        if parent:
            parent.appendChild(element)

        if value:
            element_value = self.xml.createTextNode(str(value))
            element.appendChild(element_value)
            
        return element

    def display(self):
        """Returns the formatted XML document."""
        return self.xml.toprettyxml('')

    def create_site_info(self, title, url, description):
        """Populates the site information."""
        self._create_element('title', self.channel, title)
        self.site = url
        self._create_element('link', self.channel, url)
        self._create_element('description', self.channel, description)
        self._create_element('pubDate', self.channel, datetime.utcnow())
        self._create_element('generator', self.channel, 'm2wp.py')
        self._create_element('language', self.channel, 'en')

    def create_category(self, nicename, name=""):
        """Creates a Category."""
        if name != "":
            category = self._create_element('wp:category', self.channel)
            self._create_element('wp:category_nicename', category, nicename)
            self._create_element('wp:category_parent', category)
            element = self._create_element('wp:cat_name', category)
            self._cdata(name, element)

    def create_tag(self, name):
        """Creates a Tag."""
        newtag = self._create_element('wp:tag', self.channel)
        self._create_element('wp:tag_slug', newtag, name)
        element = self._create_element('wp:tag_name', newtag)
        self._cdata(name, element)

    def create_item(self, data):
        """Creates an item from the row returned by the query."""
        linkpath = data[10].strftime('%Y/%m/%d')
        link = "%s/%s/%s" % (self.site, linkpath, data[4])
        item = self._create_element('item', self.channel)
        self._create_element('title', item, data[3])
        self._create_element('link', item, link)
        self._create_element('pubDate', item, data[10].strftime('%a, %d %b %Y %H:%M%S +0000'))
        
        author_cursor = self.connection.cursor()
        author_cursor.execute("""SELECT login FROM users WHERE id = %d;""" % data[2])
        row = author_cursor.fetchall()[0]
        self._create_element('dc:creator', item, row[0])

        self.item_categories(item, data[0])
        self.item_tags(item, data[0])
        guid = self._create_element('guid', item, link)
        guid.setAttribute('isPermaLink', 'true')
        self._create_element('description', item)
        if data[7] == '':
            content = data[8]
        else:
            content = """%s

            <!--more-->

            %s""" % (data[7], data[8])
        element = self._create_element('content:encoded', item)
        self._cdata(content, element)
        self._create_element('wp:post_id', item, data[0])
        self._create_element('wp:post_date', item, data[11])
        self._create_element('wp:post_date_gmt', item, data[11])
        if data[22] > 0:
            comments = 'open'
        else:
            comments = 'closed'
        self._create_element('wp:comment_status', item, comments)
        self._create_element('wp:ping_status', item, 'open')
        self._create_element('wp:post_name', item, data[4])
        self._create_element('wp:status', item, 'publish')
        self._create_element('wp:post_parent', item, '0')
        self._create_element('wp:menu_item', item, '0')
        self._create_element('wp:post_type', item, 'post')
        self.item_comments(item, data[0])

    def item_categories(self, item, item_id):
        """Links an item to categories."""
        cursor = self.connection.cursor()
        cursor.execute("""SELECT b.name FROM assigned_sections AS a INNER JOIN
        sections AS b ON a.section_id = b.id WHERE a.article_id = %d;""" %
            item_id)
        rows = cursor.fetchall()
        for row in rows:
            element = self._create_element('category', item)
            self._cdata(row[0], element)

    def item_tags(self, item, item_id):
        """Links an item to tags."""
        cursor = self.connection.cursor()
        cursor.execute("""SELECT b.name FROM taggings AS a INNER JOIN tags AS b
        ON a.tag_id = b.id WHERE a.taggable_id = %d;""" % item_id)
        rows = cursor.fetchall()
        for row in rows:
            tags = row[0].split(',')
            for tag in tags:
                element = self._create_element('category', item)
                element.setAttribute('domain', 'tag')
                self._cdata(tag, element)

    def item_comments(self, item, item_id):
        """Creates comments for an item."""
        cursor = self.connection.cursor()
        cursor.execute("""SELECT *  FROM contents WHERE article_id = %d;""" %
            item_id)
        rows = cursor.fetchall()
        for row in rows:
            comment = self._create_element('wp:comment', item)
            self._create_element('wp:comment_id', comment, row[0])
            element = self._create_element('wp:comment_author', comment)
            self._cdata(row[13], element)
            self._create_element('wp:comment_author_email', comment, row[15])
            self._create_element('wp:comment_author_url', comment, row[14])
            self._create_element('wp:comment_author_IP', comment, row[16])
            self._create_element('wp:comment_date', comment, row[11])
            self._create_element('wp:comment_date_gmt', comment, row[11])
            self._create_element('wp:comment_content', comment, row[6])
            self._create_element('wp:comment_approved', comment, '1')
            self._create_element('wp:comment_type', comment)
            self._create_element('wp:comment_parent', comment, '0')
    
    def _cdata(self, data, parent):
        """Helper function for creating CDATA sections."""
        cdata = self.xml.createCDATASection(data)
        parent.appendChild(cdata)

    def finalise(self):
        """Final cleanup."""
        wxr = self.display()
        return re.sub('>\n<!', '><!', wxr)

class Exporter(object):
    """Handles the exporting process."""

    def __init__(self, options):
        if options.password:
            self.dsn = "dbname='%s' user='%s' password='%s' host='%s'" % (
                options.database, options.username, options.password,
                options.server)
        else:
            self.dsn = "dbname='%s' user='%s' host='%s'" % (
                options.database, options.username, options.server)
        self.output_file = options.out
        self.opts = options
        self.connection = self._connect()
        self.wxr = Export(self.connection)

    def _connect(self):
        """Creates a database connection."""
        try:
            connection = MySQLdb.connect(db=self.opts.database, user=self.opts.username, passwd=self.opts.password, host=self.opts.server)
        except(MySQLdb.OperationalError):
            sys.exit("I am unable to connect to the database. Sorry.")

        return connection

    def _process_sites(self):
        """Handles site information."""
        cursor = self.connection.cursor()
        cursor.execute("""SELECT * FROM sites""")
        row = cursor.fetchall()[0]
        self.wxr.create_site_info(row[1], row[8], row[2])

    def _process_sections(self):
        """Handles sections (categories)."""
        cursor = self.connection.cursor()
        cursor.execute("""SELECT * FROM sections""")
        rows = cursor.fetchall()
        for row in rows:
            self.wxr.create_category(row[7], row[1]) 

    def _process_tags(self):
        """Handles tags."""
        cursor = self.connection.cursor()
        cursor.execute("""SELECT name FROM tags""")
        rows = cursor.fetchall()
        tags = []
        for row in rows:
            tags += row[0].split(',')
        
        tags = list(set(tags))
        for tag in tags:
            self.wxr.create_tag(tag) 
    
    def _process_contents(self):
        """Handles contents (items)."""
        cursor = self.connection.cursor()
        cursor.execute("""SELECT * FROM contents WHERE type = 'Article' and published_at is not null""")
        rows = cursor.fetchall()
        for row in rows:
            self.wxr.create_item(row)

    def export(self):
        """Generates the WXR."""
        self._process_sites()
        self._process_sections()
        self._process_tags()
        self._process_contents()
        output = self.wxr.finalise()

        if self.output_file:
            out = open(self.output_file,'w')
            out.write(output)
            out.close()
        else:
            print output


def parseoptions(args):
    """Parses command line options."""
    parser = OptionParser()
    parser.add_option("-d", "--database", default="", type="string",
                      help="The name of the database you want to connect to.")
    parser.add_option("-s", "--server", default="localhost", type="string",
                      help="The name of the server you want to connect to.")
    parser.add_option("-u", "--username", default="", type="string",
                      help="The username to connect to the database with.")
    parser.add_option("-p", "--password", type="string",
                      help="The password to connect to the database with.")
    parser.add_option("-o", "--out", type="string",
                      help="The filename where you want the output stored.")
    return parser.parse_args(args)[0]

if __name__ == '__main__':
    options = parseoptions(sys.argv)
    exporter = Exporter(options)
    exporter.export()
