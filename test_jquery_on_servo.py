#!/usr/bin/env python

import os
import re
import subprocess
import sys
import BaseHTTPServer
import SimpleHTTPServer
import SocketServer
import threading
import urlparse

JQUERY_MODULES = [
    #"ajax",            # panics
    "attributes",
    "callbacks",
    #"core",            # mozjs crash
    "css",
    "data",
    "deferred",
    "dimensions",
    "effects",
    #"event",           # panics
    #"manipulation",    # mozjs crash
    "offset",
    "queue",
    "selector",
    "serialize",
    "support",
    "traversing",
    "wrap"
]

TEST_SERVER_PORT = 8192

REGEX_PATTERN = "^\[jQuery test\] \[([0-9]+)/([0-9]+)/([0-9]+)] (.*)"

SERVO_EXE = "../servo/components/servo/target/release/servo"


class TestResult:
    def __init__(self, success, fail, total, text):
        self.success = int(success)
        self.fail = int(fail)
        self.total = int(total)
        self.text = text

    def __key(self):
        return (self.success, self.fail, self.total, self.text)

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __ne__(self, other):
        return self.__key() != other.__key()

    def __hash__(self):
        return hash(self.__key())

    def __repr__(self):
        return "ok={0} fail={1} total={2}".format(self.success, self.fail, self.total)


def parse_line_to_result(line):
    match = re.match(REGEX_PATTERN, line)
    success, fail, total, name = match.groups()
    return name, TestResult(success, fail, total, line)


def parse_string_to_results(buffer):
    test_results = {}
    lines = buffer.splitlines()
    for line in lines:
        name, test_result = parse_line_to_result(line)
        test_results[name] = test_result
    return test_results


def run_servo(module):
    url = "http://localhost:{0}/test/?module={1}".format(TEST_SERVER_PORT, module)
    args = [ SERVO_EXE, url, "-z" ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    while True:
        line = proc.stdout.readline()
        if len(line) == 0:
            break
        line = line.rstrip()
        try:
            name, test_result = parse_line_to_result(line)
            yield name, test_result
        except AttributeError:
            pass

def module_filename(module):
    return 'jquery_expected_{0}.txt'.format(module)


def read_existing_results(module):
    with open(module_filename(module), 'r') as file:
        buffer = file.read()
        return parse_string_to_results(buffer)


def write_results(module, results):
    with open(module_filename(module), 'w') as file:
        for result in test_results.itervalues():
            file.write(result.text + '\n')


def print_usage():
    print("USAGE: {0} test|update".format(sys.argv[0]))


def run_http_server():
    class ThreadingSimpleServer(SocketServer.ThreadingMixIn,
                                BaseHTTPServer.HTTPServer):
        allow_reuse_address = True

    class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
        # TODO(gw): HACK copy the fixed version from python
        # main repo - due to https://bugs.python.org/issue23112
        def send_head(self):
            path = self.translate_path(self.path)
            f = None
            if os.path.isdir(path):
                parts = urlparse.urlsplit(self.path)
                if not parts.path.endswith('/'):
                    # redirect browser - doing basically what apache does
                    self.send_response(301)
                    new_parts = (parts[0], parts[1], parts[2] + '/',
                                 parts[3], parts[4])
                    new_url = urlparse.urlunsplit(new_parts)
                    self.send_header("Location", new_url)
                    self.end_headers()
                    return None
                for index in "index.html", "index.htm":
                    index = os.path.join(path, index)
                    if os.path.exists(index):
                        path = index
                        break
                else:
                    return self.list_directory(path)
            ctype = self.guess_type(path)
            try:
                # Always read in binary mode. Opening files in text mode may cause
                # newline translations, making the actual size of the content
                # transmitted *less* than the content-length!
                f = open(path, 'rb')
            except IOError:
                self.send_error(404, "File not found")
                return None
            try:
                self.send_response(200)
                self.send_header("Content-type", ctype)
                fs = os.fstat(f.fileno())
                self.send_header("Content-Length", str(fs[6]))
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()
                return f
            except:
                f.close()
                raise

        def log_message(self, format, *args):
            return

    server = ThreadingSimpleServer(('', TEST_SERVER_PORT), RequestHandler)
    while True:
        sys.stdout.flush()
        server.handle_request()

if __name__ == '__main__':
    if not os.path.isfile(SERVO_EXE):
        print("Unable to find {0}. This script expects a release build of Servo.".format(SERVO_EXE))
        sys.exit(1)

    if len(sys.argv) == 2:
        # Start the test server
        httpd_thread = threading.Thread(target=run_http_server)
        httpd_thread.setDaemon(True)
        httpd_thread.start()

        if sys.argv[1] == "test":
            print("Testing jQuery on Servo!")
            test_count = 0
            unexpected_count = 0

            individual_success = 0
            individual_total = 0

            for module in JQUERY_MODULES:
                print("\t{0}".format(module))

                prev_test_results = read_existing_results(module)
                for name, current_result in run_servo(module):
                    test_count += 1
                    individual_success += current_result.success
                    individual_total += current_result.total
                    if name in prev_test_results:
                        prev_result = prev_test_results[name]
                        if prev_result == current_result:
                            print("\t\tOK: {0}".format(name))
                        else:
                            unexpected_count += 1
                            print("\t\tFAIL: {0}: WAS {1} NOW {2}".format(name, prev_result, current_result))
                        del prev_test_results[name]
                    else:
                        unexpected_count += 1
                        print("\t\tNEW: {0}".format(current_result.text))

                for name in prev_test_results:
                    test_count += 1
                    unexpected_count += 1
                    print("\t\tMISSING: {0}".format(prev_test_results[name].text))

            print("\tRan {0} test groups. {1} unexpected results.".format(test_count, unexpected_count))
            print("\t{0} tests succeeded of {1} ({2:.2f}%)".format(individual_success, individual_total, 100.0 * individual_success / individual_total))
            if unexpected_count > 0:
                sys.exit(1)
        elif sys.argv[1] == "update":
            print("Updating jQuery expected results")
            for module in JQUERY_MODULES:
                print("\t{0}".format(module))
                test_results = {}
                for name, test_result in run_servo(module):
                    print("\t\t{0} {1}".format(name, test_result))
                    test_results[name] = test_result
                write_results(module, test_results)
        else:
            print_usage()
    else:
        print_usage()
