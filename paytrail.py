#!/usr/bin/python
# -*- coding: utf-8 -*-

import requests
from requests.auth import HTTPBasicAuth
from xml.dom import minidom
import json
import logging
from md5 import md5

contact = {
    'first_name': 'Firstname',
    'last_name': 'Lastname',
    'email': 'example@example.com',
    'street': 'Some Street 12',
    'postalcode': '31337',
    'postalcity': 'Elite',
    'country': 'IF',
    'telephone': '',
    'mobile': '0123456789',
    'company': 'AwesomeCompany Ltd.'
}

urlset = {
    'success': 'http://localhost/payment/success',
    'failure': 'http://localhost/payment/failure',
    'notification': 'http://localhost/payment/notify',
    'pending': 'http://localhost/payment/pending',
}


order_number = 1


class Product(object):
    COST_TYPE_NORMAL = 1
    COST_TYPE_POSTAL = 2
    COST_TYPE_HANDLING = 3

    def __init__(self, product_id, title, amount, price, vat, discount,
                 cost_type=COST_TYPE_NORMAL):
        self.product_id = product_id
        self.title = title
        self.amount = amount
        self.price = price
        self.vat = vat
        self.discount = discount
        self.cost_type = cost_type


class Payment(object):
    def __init__(self, order_number, contact, urlset):
        self.order_number = order_number
        self.reference_number = ""
        self.description = ""
        self.currency = "EUR"
        self.locale = "fi_FI"
        self.contact = contact
        self.urlset = urlset
        self.include_vat = 1
        self.products = []

    def add_product(self, product_id, product_name, amount,
                    price, vat, discount):
        self.products.append(Product(product_id, product_name, amount,
                                     price, vat, discount))

    def get_json_data(self):
        data = {}
        data["orderNumber"] = self.order_number
        data["referenceNumber"] = self.reference_number
        data["description"] = self.description
        data["currency"] = self.currency
        data["locale"] = self.locale
        data["urlSet"] = self.urlset
        data["orderDetails"] = {
            "includeVat": self.include_vat,
            "contact": {
                "firstName": self.contact.get("first_name"),
                "lastName": self.contact.get("last_name"),
                "email": self.contact.get("email"),
                "mobile": self.contact.get("mobile"),
                "telephone": self.contact.get("telephone"),
                "companyName": self.contact.get("companyName"),
                "address": {
                    "street": self.contact.get("street"),
                    "postalCode": self.contact.get("postalcode"),
                    "postalOffice": self.contact.get("postalcity"),
                    "country": self.contact.get("country"),
                }
            },
            "products": [],
        }
        for product in self.products:
            data["orderDetails"]["products"].append({
                "title": product.title,
                "code": product.product_id,
                "amount": product.amount,
                "price": product.price,
                "vat": product.vat,
                "discount": product.discount,
                "type": product.cost_type
            })

        return data


class Paytrail(object):
    def __init__(self, merchant_id, merchant_secret,
                 service_url="https://payment.paytrail.com"):
        self.merchant_id = merchant_id
        self.merchant_secret = merchant_secret
        self.service_url = service_url

    def process_payment(self, payment):
        url = self.service_url + "/token/json"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Verkkomaksut-Api-Version": "1"
        }
        data = payment.get_json_data()
        url = self.service_url + "/api-payment/create"
        result = requests.post(url, data=json.dumps(data), headers=headers,
                               auth=HTTPBasicAuth(self.merchant_id,
                                                  self.merchant_secret))

        if result.status_code != 201:
            if result.headers['content-type'] == "application/xml":
                errordoc = minidom.parseString(result.text)
                error_message = ','.join(
                    x.toprettyxml() for x
                    in errordoc.getElementsByTagName('errorMessage'))
                error_code = ','.join(
                    x.toprettyxml() for x
                    in errordoc.getElementsByTagName('errorCode'))
                raise Exception('Paytrail::Exception %s [%s]' %
                                (error_message, error_code))
            elif result.headers['content-type'] == "application/json":
                errordoc = json.loads(result.text)
                error_message = errordoc.get('errorMessage')
                error_code = errordoc.get('errorCode')
                raise Exception('Paytrail::Exception %s [%s]' %
                                (error_message, error_code))
        data = json.loads(result.text)
        if not data:
            raise Exception("unknown-error %s [%s]" %
                            (result.text, result.status_code))

        return {"token": data.get('token'), "url": data.get('url')}

    def confirm_payment(self, order_number, timestamp, paid, method,
                        auth_code):
        base = "%s|%s|%s|%s|%s" % (order_number, timestamp, paid, method,
                                   self.merchant_secret)
        base_encoded = md5(base).hexdigest().upper()
        valid = auth_code == base_encoded
        if not valid:
            logging.warn("returned auth_code differs from calculated %s != %s" %
                         (auth_code, base_encoded))
        return valid


def main():
    import httplib

    httplib.HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
    import traceback
    payment = Payment(order_number, contact, urlset)
    payment.add_product("0001", "Test Product", "1.00", "4.99", "23.00", "0.00")
    # Paytrail test credentials
    # http://support.paytrail.com/hc/en-us/articles/201571876-Test-credentials-to-test-service
    paytrail = Paytrail("13466", "6pKF4jkv97zmqBJ3ZL8gUw5DfT2NMQ")
    try:
        result = paytrail.process_payment(payment)
    except Exception as exp:
        traceback.print_exc()
        logging.error("Exception: %s" % exp)
    else:
        logging.info(result)

if __name__ == '__main__':
    main()
