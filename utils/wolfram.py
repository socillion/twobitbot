#!/usr/bin/env python

import logging
import re
import tungsten

from twisted.internet import threads

log = logging.getLogger(__name__)


class WolframAlphaError(Exception):
    pass


class WolframAlphaAPIError(WolframAlphaError):
    def __init__(self, message, code):
        super(WolframAlphaAPIError, self).__init__(message)
        self.code = code


class WolframAlphaTimeoutError(WolframAlphaError):
    pass


class WolframAlpha(object):
    """wrapper around Tungsten"""
    def __init__(self, app_id):
        self.tungsten = tungsten.Tungsten(app_id)

    def query(self, query):
        """:type query: basestring"""

        def process_results(results):
            """:type results: tungsten.Result"""
            pods = results.pods
            result_metadata = results.xml_tree.getroot()
            if pods:
                for pod in pods:
                    if pod.root.get('primary'):
                        # todo look into situations w/ multiple pods tagged as primary
                        answer = ' '.join(pod.format['plaintext'])
                        break
                else:
                    answer = ' '.join(pods[0].format['plaintext'])

                #########################################
                # todo this solution is pretty dirty, try to find better
                # wolfram alpha returns strings in the form of '\:0e3f' to represent
                # unicode characters. Replace those with real unicode chars.
                unencoded_chars = re.finditer(r"\\:([0-9a-f]{4})", answer, re.MULTILINE)
                for char in unencoded_chars:
                    position = char.span()
                    codepoint = unichr(int(char.group(1), base=16))
                    answer = answer[:position[0]] + codepoint + answer[position[1]:]
                #########################################

                return answer

            elif results.error:
                msg = results.error
                error = results.xml_tree.find('error')
                if error:
                    code = error.find('code').text
                else:
                    code = -1
                log.info("Wolfram|Alpha query '{}' errored out with code {}: '{}'".format(query, code, msg))
                raise WolframAlphaAPIError(msg, code)

            elif result_metadata.get('timedout') or result_metadata.get('parsetimedout'):
                log.debug("Wolfram|Alpha query timed out: '{}'".format(query))
                raise WolframAlphaTimeoutError("your query timed out")

            else:
                # not sure what happened. No error, no timeout, no results set.
                # Haven't seen this yet.
                log.error("Something went wrong while querying wolfram "
                          "alpha. Query: {}".format(query))

        def handle_error(fail):
            """:type fail: twisted.internet.defer.failure.Failure"""
            # with tungsten this probably only raises an exception if
            # it's an HTTP error (encoding or response code)
            log.error("Unexpected Exception with Wolfram|Alpha API (Tungsten): {}".format(fail.getErrorMessage()))
            # re-raise
            return fail

        # todo make timeouts more reliable (e.g. "!wolfram define futures"
        # times out on the first call but not on subsequent)
        d = threads.deferToThread(self.tungsten.query, query)
        d.addCallbacks(process_results, handle_error)
        return d
