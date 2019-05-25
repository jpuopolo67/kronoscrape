# -*- coding: utf-8 -*-
import scrapy
from scrapy.crawler import CrawlerProcess
import pprint
import boto3
from botocore.exceptions import ClientError
import os
import shutil
import difflib
import json


class KengjobsSpider(scrapy.Spider):

    name = 'kengjobs'
    allowed_domains = ['kronos.com']
    start_urls = ['https://careers.kronos.com/careers/SearchJobs/?3_86_3=%5B%2246987%22%5D&3_35_3=28277']
        # This URL yields all of the Engineering jobs in Lowell, MA

    def __init__(self):
        super(scrapy.Spider, self).__init__()
        self._count = 1
        self._interesting_titles = ['Director', 'VP', 'President']

    def parse(self, response):
        print(f'Crawling: {response.url}')

        job_listings = response.css('li.listSingleColumnItem')
        for job_listing in job_listings:
            job_title = job_listing.css('.listSingleColumnItemTitle a::text').extract_first()
            job_href = job_listing.css('.listSingleColumnItemTitle a::attr(href)').extract_first()
            ref_id = job_listing.css('.listSingleColumnItemMiscData span::text').extract()[2].strip('. ')

            for title in self._interesting_titles:
                if title in job_title:
                    job = {
                        'job_count': self._count,
                        'title': job_title,
                        'link': job_href,
                        'ref_id': ref_id
                    }
                    pprint.pprint(job)
                    self._count +=1

                    yield job
                    break

        # When we're done processing a page, get a link to the next page
        next_page_url = response.css('.paginationItem:last-child::attr(href)').extract_first()
        if next_page_url:
            yield scrapy.Request(url=next_page_url, callback=self.parse)


def main(event, context):

    # Tell Scrapy to output the scraped results to kjobs.json
    OUTFILE = 'kjobs.json'

    # Remove old output file or else Scrapy will append to it
    if os.path.exists(OUTFILE):
        os.unlink(OUTFILE)

    # Crawl, spider, crawl
    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)',
        'FEED_FORMAT': 'json',
        'FEED_URI': OUTFILE
    })
    process.crawl(KengjobsSpider)
    process.start() # script blocks here until the crawling is finished

    # If this is the first run (no previous output file), copy the current
    # output file so we have 2 good files to compare
    if not os.path.exists('kjobs-prev.json'):
        shutil.copyfile(OUTFILE, 'kjobs-prev.json')

    # Compare the current output file to the previous to detect any changes.
    with open(OUTFILE) as f:
        kjobs_file_contents = f.readlines()
        f.seek(0)
        kjobs_json = f.read()
    with open('kjobs-prev.json') as f:
        kjobs_prev_contents = f.readlines()
    diffs = list(difflib.unified_diff(kjobs_file_contents, kjobs_prev_contents))

    # If there are changes since the last time the spider was run, email me
    if len(diffs):
        email_me(kjobs_json)

    # Make the previous file the current file so that if the next run is
    # identical, we're not sending out email after email
    shutil.copyfile(OUTFILE, 'kjobs-prev.json')
    print("Crawl complete!")

def email_me(jobs_json):

    html_content = "<html><head></head><body>"
    html_content += "<h2>Interesting Jobs @ Kronos</h2>"
    html_content += "<ul>"

    jobs_list = json.loads(jobs_json)
    for job in jobs_list:
        job_li = "<li>{}, {}<br/>{}</li>".\
            format(job['title'], job['ref_id'], job['link'])
        html_content += job_li

    html_content += "</ul>"
    html_content += "<p>Love,<br/>Youself</p>"
    html_content += "</body></html>"

    SENDER = "John Puopolo <puopolo@gmail.com>"
    RECIPIENT = "puopolo@gmail.com"
    AWS_REGION = "us-east-1"
    SUBJECT = "New Engineering Jobs at Kronos"

    # The HTML body of the email.
    BODY_HTML = html_content

    # The character encoding for the email.
    CHARSET = "UTF-8"

    # Create a new SES resource
    client = boto3.client('ses',region_name=AWS_REGION)

    # Try to send the email
    try:
        response = client.send_email(
            Destination = {
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message = {
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source = SENDER,
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])

# AWS Lambda test
if __name__ == "__main__":
    main('', '')
