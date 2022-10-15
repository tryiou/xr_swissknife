import json
import os
import pickle
import time
from datetime import datetime
from threading import Thread
import subprocess
import dictdiffer
import requests

import config

ROOT_DIR = os.path.abspath(os.curdir)
date_last_call = {}
callpersecond = 50


def write_data(filename, data):
    try:
        with open(ROOT_DIR + "/" + filename, 'wb') as file:
            pickle.dump(data, file)
    except Exception as e:
        print("Exception:", type(e), str(e))


def read_data(filename):
    try:
        with open(ROOT_DIR + "/" + filename, 'rb') as file:
            result = pickle.load(file)
    except Exception as e:
        print("Exception:", type(e), str(e))
        result = []
    return result


def rpc_call(method, params=None, endpoint=None, display_res=1):
    # rpc_call for /xrs/ endpoint only
    global date_last_call
    org_endpoint = endpoint
    if params is None:
        params = []
    if endpoint[-1] == '/':
        endpoint = endpoint + method
    else:
        print("rpc_call, endpoint error", endpoint, method)
        exit()

    headers = {
        # Already added when you pass json=
        # 'content-type': 'application/json',
    }
    if type(params) == str:
        json_data = [params]
    elif type(params) == list:
        json_data = params
    else:
        json_data = []
    # call per second limiter>>
    timetowait = 60 / callpersecond
    if date_last_call and org_endpoint in date_last_call:
        while (datetime.now() - date_last_call[org_endpoint]).total_seconds() < timetowait:
            sleep = 0.1
            time.sleep(sleep)

    # call per second limiter<<
    t1 = time.perf_counter()
    done = False
    counter = 0
    while not done:
        try:
            counter += 1
            response = requests.post(endpoint, headers=headers, json=json_data, timeout=60).text
            date_last_call[org_endpoint] = datetime.now()
            # print(response)
            tojson = json.loads(response)
            response = tojson
        except json.decoder.JSONDecodeError as e:
            # print("rpc_call", response, counter, type(e), e)
            pass
        except Exception as e:
            print("rpc_call", type(e), e)
            response = None
        finally:
            t2 = time.perf_counter()
            if display_res >= 1:
                print(endpoint, params, t2 - t1, "s")
            if display_res > 1:
                print(response)
                # print("perf_counter:", t2 - t1, "s")
            if response and type(response) is str and "429 Too Many Requests" in response:
                print(counter, response)
                time.sleep(counter * 20)
            else:
                return response


def get_chainz_summary():
    chainz_url = "https://chainz.cryptoid.info/explorer/api.dws?q=summary"
    count = 0
    maxi = 3
    while 1:
        count += 1
        if count == maxi:
            return None
        try:
            result = requests.get(chainz_url).json()
        except Exception as e:
            print("chainz_summary error:\n" + str(type(e)) + "\n" + str(e))
            time.sleep(0.5)
        else:
            return result


def check_getblockcount_cc_chainz():
    endpoint = config.cc_endpoint1
    heights = rpc_call('heights', endpoint=endpoint)
    print(heights.keys())
    cc_coins = heights.keys()  # ["BLOCK", "SYS", "LTC", "RVN"]
    tolerance = 10
    msg_format = f"{' coin':<7} | {'cc':<9} | {'chainz':<9} | {'valid'}"
    # print(chainz_sum)
    counter = 0
    false_list = read_data('data.pic')
    # list_to_mail = []
    while 1:
        counter += 1
        chainz_sum = get_chainz_summary()
        now = datetime.now()
        print("\n" + now.strftime("%m/%d/%Y, %H:%M:%S"), counter, counter % 5)
        print(msg_format)
        for coin in cc_coins:
            if chainz_sum and coin.casefold() in chainz_sum:
                chainz_height = int(chainz_sum[coin.casefold()]['height'])
            else:
                try:
                    chainz_height = int(
                        rpc_call("xrgetblockcount", endpoint=config.xr_endpoint1 + coin + "/"))
                except Exception as e:
                    print(type(e), str(e))
                    chainz_height = None
            cc_height = rpc_call('getblockcount', coin, endpoint=endpoint, display_res=0)
            if cc_height:
                try:
                    toint = int(cc_height)
                    cc_height = toint
                except TypeError as e:
                    cc_height = None
                except Exception as e:
                    print(type(e), str(e), cc_height)
                    cc_height = None
            valid = False
            if chainz_height and cc_height:
                if chainz_height + tolerance >= cc_height >= chainz_height - tolerance:
                    valid = True
            if not valid:
                false_list.append(
                    {'date': now.strftime("%m/%d/%Y, %H:%M:%S"), 'coin': coin, 'cc_height': cc_height,
                     'chainz_height': chainz_height, 'valid': valid})
                write_data('data.pic', false_list)
                print(subprocess.call([ROOT_DIR + "/discord_alert.py", str(false_list[-1])]))
            msg = f"{' ' + coin:<7} | {str(cc_height):<9} | {str(chainz_height):<9} | {valid}"
            print(msg)
        time.sleep(60)
        if len(false_list) > 0:
            if counter % 5 == 0:
                for each in false_list:
                    print(each)



#            print(false_list)


getutxos_addresses = {"BLOCK": ["BfMkEpJy3EAQit4rs9j38MkRTJT9LBWedg"],
                      "SYS": ["SfufiQU7JNyFuv5UDMxVxP1HspdGpx8WUP"],
                      "DOGE": ["DBKkVK9YwZvcjEBt8SRrN9WrnhryBVdu28", "DHQsfy66JsYSnwjCABFN6NNqW4kHQe63oU",
                               "DHQsfy66JsYSnwjCABFN6NNqW4kHQe63oU"],
                      "LTC": ["LP98Q2gPZ9gUhoL5fDji357HPRHxVqWh6j", "M8T1B2Z97gVdvmfkQcAtYbEepune1tzGua",
                              "MQTGsZHA96Smwjiz6RRTrsrRMo65q2JKbR"],
                      "DASH": ["XdAUmwtig27HBG6WfYyHAzP8n6XC9jESEw", "XnT33zjrFKjt3ymfyQZs2FPiKNer3WVj14",
                               "Xmuyhh1WEAW5w8HRT15sTsdVpkkZ3DtrnR"],
                      "PIVX": ["DKFuxPKion9RwCaCh8p9oqqUFcRhuVNGw4", "DPB4BvsjgyBEPFs3AA6Fg32ut1niKxjrL1",
                               "DBa5cB3hMns5kwrdWVuCx9JjR5s5sVCY7U"],
                      "BTC": ["1LQoWist8KkaUXSPKZHNvEyfrEkPHzSsCd", "37XuVSEpWW4trkfmvWzegTHQt7BdktSKUs",
                              "35PPdr9CSZuqwi2S7vj9ResHQCVTsYuB3z"],
                      "RVN": ["RQuitt1kViGLqPs6JWtxKPTmf3m9YGFdyC", "RE3V4ck6mD5Xd6Kvk5X5mgqdGFDB4V3ZKC",
                              "RLmTnB2wSNbSi5Zfz8Eohfvzna5HR2qxk3"]}
getrawtransaction_txids = {"BLOCK": "eb1b47227704d30df544a72bbb6466a541a70880468026a7576e6acfbe75dd22",
                           "SYS": "fd9f6ce7b2c80b970ba48c2d634750c8f038bb35482fed04061858551d55bed2",
                           "DOGE": "0d9c20008842d12ef2dad3072001c2d810dc730a569c2be355f8e0956e1ba4bc",
                           "LTC": "af13eb124aad27d1b818389208f26e01be2949d485a435bcb4414fe643936d07",
                           "DASH": "b686d3d6be7cd6955688ea1df305d919b7dfafd21b65dddfb1e38aeffc0e0b6a",
                           "PIVX": "c43c70f197afad7e4331e3401199c555a954b0eec2797211dcc9fba3ad667dae",
                           "BTC": "bce9a324598fa154b7ac94f778c5c9011c1d654509043afe19c0638fbb63e500",
                           "RVN": "0f9925f13f2cf6a43a135dacfacd4b32246a14ee7d9834b651d5cd4d99cf7d3e"}


def test_sequence(endpoint=None, block_to_check=300000, coin=None, result={}):
    display_res = 1
    # coin_to_test = rpc_call('heights').keys()
    # result = {}
    # for coin in coin_to_test:
    a_getblockhash = None
    a_getblock = None
    a_rawtx = None
    a_getutxos = None
    a_balance = None
    a_gethistory = None
    address = None

    a_getblockhash = getblockhash(coin, block_to_check, endpoint)
    if type(a_getblockhash) is str:
        a_getblock = getblock(coin, a_getblockhash, endpoint)
    if a_getblock and 'tx' in a_getblock:
        a_rawtx = getrawtransaction(coin, a_getblock['tx'][-1], endpoint)
        # print(a_rawtx['vout'][1]['scriptPubKey'])
        done = False
        id = 0
        while not done:
            try:
                address = a_rawtx['vout'][id]['scriptPubKey']['addresses'][-1]
            except IndexError as e:
                address = None
                done = True
            except Exception as e:
                # print("address", id, type(e), str(e), a_rawtx['vout'])
                id += 1
                pass
            else:
                done = True
        if address:
            a_getutxos = getutxos(coin, address, endpoint)
            a_balance = getbalance(coin, address, endpoint)
            a_gethistory = gethistory(coin, address, endpoint)
            # print(a_gethistory)
    result[coin] = {'getutxos': a_getutxos,
                    'getrawtransaction': a_rawtx,
                    # 'getrawmempool': getrawmempool(coin,endpoint),
                    # 'getblockcount': res_getblockcount,
                    # 'gettransaction': gettransaction(coin, getrawtransaction_txids[coin],endpoint),
                    'getblockhash': a_getblockhash,
                    'getblock': a_getblock,
                    'getbalance': a_balance,
                    'gethistory': a_gethistory
                    }

    # return result
    # a_rawtx = getrawtransaction(coin_to_test[0], )
    # print(a_getblockhash)


def compare_test_sequence(start_block=100, stop_block=103, coin_to_test=["BLOCK"]):
    endpoint1 = config.exr_endpoint1
    endpoint2 = config.exr_endpoint2
    final = {}
    result1 = {}
    result2 = {}
    for block in range(start_block, stop_block + 1):
        for coin in coin_to_test:
            print("COIN:", coin, "BLOCK:", block)
            t1 = Thread(target=test_sequence, args=(endpoint1, block, coin, result1,))
            t2 = Thread(target=test_sequence, args=(endpoint2, block, coin, result2,))
            # final[block]
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            # test_sequence(endpoint1, block, coin, result1)
            # test_sequence(endpoint2, block, coin, result2)
            compare_results(result1, result2)

# OLD
# def test_cc_calls():
#     endpoint1 = config.exr_endpoint1
#     endpoint2 = config.exr_endpoint2
#     coin_to_test = ["BLOCK", "SYS"]
#     display_res = 2
#     result1 = {}
#     result2 = {}
#     # TEST DATA
#     url = endpoint1
#     result1['ping'] = ping(endpoint1)
#     result1['fees'] = fees(endpoint1)
#     result1['heights'] = heights(endpoint1)
#     url = endpoint2
#     result2['ping'] = ping(endpoint2)
#     result2['fees'] = fees(endpoint2)
#     result2['heights'] = heights(endpoint2)
#     # for coin in res_heights1.keys():
#     for coin in coin_to_test:
#         url = endpoint1
#         res_getblockcount = getblockcount(coin, endpoint1)
#         res_getblockhash = getblockhash(coin, res_getblockcount, endpoint1)
#         res_getblock = getblock(coin, res_getblockhash, endpoint1)
#         result1[coin] = {'getutxos': getutxos(coin, getutxos_addresses[coin], endpoint1),
#                          'getrawtransaction': getrawtransaction(coin, getrawtransaction_txids[coin], endpoint1),
#                          'getrawmempool': getrawmempool(coin, endpoint1),
#                          'getblockcount': res_getblockcount,
#                          'gettransaction': gettransaction(coin, getrawtransaction_txids[coin], endpoint1),
#                          'getblockhash': res_getblockhash,
#                          'getblock': res_getblock,
#                          'getbalance': getbalance(coin, getutxos_addresses[coin][0], endpoint1),
#                          'gethistory': gethistory(coin, getutxos_addresses[coin][0], endpoint1)
#                          }
#         url = endpoint2
#         res_getblockcount = getblockcount(coin, endpoint2)
#         res_getblockhash = getblockhash(coin, res_getblockcount, endpoint2)
#         res_getblock = getblock(coin, res_getblockhash, endpoint2)
#         result2[coin] = {'getutxos': getutxos(coin, getutxos_addresses[coin], endpoint2),
#                          'getrawtransaction': getrawtransaction(coin, getrawtransaction_txids[coin], endpoint2),
#                          'getrawmempool': getrawmempool(coin, endpoint2),
#                          'getblockcount': res_getblockcount,
#                          'gettransaction': gettransaction(coin, getrawtransaction_txids[coin], endpoint2),
#                          'getblockhash': res_getblockhash,
#                          'getblock': res_getblock,
#                          'getbalance': getbalance(coin, getutxos_addresses[coin][0], endpoint2),
#                          'gethistory': gethistory(coin, getutxos_addresses[coin][0], endpoint2)
#                          }
#     print("compare 2 cc endpoints:", endpoint1, endpoint2)
#     compare_results(result1, result2)

    # TEST DATA
    # for coin in res_heights1.keys():


def compare_results(result1, result2, display=False):
    for each in result1:
        print(each)
        if type(result1[each]) == dict:
            if each in result2:
                for each2 in result1[each]:
                    print('   ', each2)
                    if each2 in result1[each] and each2 in result2[each]:
                        if result1[each][each2] != result2[each][each2]:
                            print('!!!difference!!!')
                            if display:
                                print("res1:", repr(result1[each][each2]))
                                print("res2:", repr(result2[each][each2]))
                                print()
                            if display:
                                for diff in list(dictdiffer.diff(result1[each][each2], result2[each][each2])):
                                    print(diff)
                                print()
                        else:
                            print('!!!same!!!')
                    else:
                        print('!!!difference!!!')
                        if display:
                            for diff in list(dictdiffer.diff(result1[each], result2[each])):
                                print(diff)
            else:
                pass
        else:
            if result1[each] != result2[each]:
                print('!!!difference!!!')
                if display:
                    print("res1:", repr(result1[each]))
                    print("res2:", repr(result2[each]))
                    print()
            else:
                print('!!!same!!!')


def ping(endpoint):
    # PING
    return rpc_call("ping", endpoint=endpoint)


def fees(endpoint):
    # FEES
    return rpc_call("fees", endpoint=endpoint)


def heights(endpoint):
    # HEIGHTS
    return rpc_call("heights", endpoint=endpoint)


def getutxos(coin, addresseslist, endpoint):
    # GETUTXOS
    return rpc_call("getutxos", [coin, addresseslist], endpoint=endpoint)


def getrawtransaction(coin, txid, endpoint):
    # GETRAWTRANSACTION
    return rpc_call("getrawtransaction", [coin, txid, True], endpoint=endpoint)


def getrawmempool(coin, endpoint):
    # GETRAWMEMPOOL
    return rpc_call("getrawmempool", coin, endpoint=endpoint)


def getblockcount(coin, endpoint):
    # GETBLOCKCOUNT
    return int(rpc_call("getblockcount", coin, endpoint=endpoint))


def gettransaction(coin, txid, endpoint):
    # GETTRANSACTION
    return rpc_call("gettransaction", [coin, txid], endpoint=endpoint)


def getblockhash(coin, height, endpoint):
    # GETBLOCKHASH
    return rpc_call("getblockhash", [coin, height], endpoint=endpoint)


def getblock(coin, blockhash, endpoint):
    # GETBLOCK
    return rpc_call("getblock", [coin, blockhash, 1], endpoint=endpoint)


def getbalance(coin, address, endpoint):
    # GETBALANCE
    return rpc_call("getbalance", [coin, address], endpoint=endpoint)


def gethistory(coin, addresseslist, endpoint):
    # GETHISTORY
    return rpc_call("gethistory", [coin, addresseslist], endpoint=endpoint)


# compare_test_sequence(400500, 400600, ["BLOCK"])
# test_cc_calls()

check_getblockcount_cc_chainz()
