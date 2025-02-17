# -*- coding=utf-8 -*-
# library: jionlp
# author: dongrixinyu
# license: Apache License 2.0
# Email: dongrixinyu.89@163.com
# github: https://github.com/dongrixinyu/JioNLP
# description: Preprocessing tool for Chinese NLP


import re

from jionlp.rule.rule_pattern import MONEY_PREFIX_STRING, \
    MONEY_KUAI_MAO_JIAO_FEN_STRING, MONEY_PREFIX_CASE_STRING, \
    MONEY_CHAR_STRING, MONEY_NUM_STRING
from jionlp.gadget.money_parser import MoneyParser


class MoneyExtractor(object):
    """ 货币金额抽取器。不依赖模型，将文本中的货币金额进行抽取，并对其做金额解析。

    Args:
        text(str): 输入待抽取货币金额的文本
        with_parsing(bool): 指示返回结果是否包含解析信息，默认为 True
        ret_all(bool): 某些货币金额表达，在大多数情况下并非表达货币金额，如 “几分” 之于 “他有几分不友善”，默认按绝大概率处理，
            即不返回此类伪货币金额表达，该参数默认为 False；若希望返回所有抽取到的货币金额表达，须将该参数置 True。

    Returns:
        list(dict): 包含货币金额的列表，其中包括 text、type、offset 三个字段，和工具包中 NER 标准处理格式一致。

    Example：
        >>> import jionlp as jio
        >>> text = '海航亏损7000万港元出售香港公寓。12月12日，据《香港经济日报》报道，' \
                '海航集团将持有的部分位于香港铜锣湾Yoo Residence大楼中的物业以2.6亿港元的价格出售'
        >>> res = jio.ner.extract_money(text, with_parsing=False)
        >>> print(res)

    """
    def __init__(self):
        self.parse_money = None

    def _prepare(self):
        self.parse_money = MoneyParser()
        # single_money_pattern = ''.join(
        #     [absence(MONEY_PREFIX_STRING),
        #      absence(MONEY_PREFIX_CASE_STRING), '(', MONEY_NUM_STRING, '+',
        #      bracket(MONEY_NUM_MIDDLE_STRING + MONEY_NUM_STRING + '+'), '*',
        #      MONEY_SUFFIX_CASE_STRING, ')+',
        #      bracket_absence(MONEY_NUM_STRING),
        #      absence(MONEY_SUFFIX_STRING)])

        # self.money_string_pattern = re.compile(single_money_pattern)
        self.qian_wan_yi_yuan_exception_check_pattern = re.compile(r'[k千仟w万萬亿]元[0-9]')
        self.money_num_string_pattern = re.compile(MONEY_NUM_STRING)
        self.money_string_pattern = re.compile(MONEY_CHAR_STRING)

        # 此类表达虽然可按货币金额解析，但是文本中很大概率并非表示货币金额，故以大概率进行排除，
        # 并设参数 ret_all，即返回所有进行控制，默认为 False，即根据词典进行删除
        # 删除性正则
        # - 单纯包含 分、角、块，而无其它格式货币的
        # - 特殊词汇如 “多元” 等
        self.money_kuai_map_jiao_fen_pattern = re.compile(MONEY_KUAI_MAO_JIAO_FEN_STRING)
        self.non_money_string_list = ['多元', '十分', '百分', '万分']

    def __call__(self, text, with_parsing=True, ret_all=False):
        if self.parse_money is None:
            self._prepare()

        candidates_list = self.extract_money_candidates(text)

        money_entity_list = list()
        for candidate in candidates_list:
            offset = [0, 0]
            bias = 0
            while candidate['offset'][0] + offset[1] < candidate['offset'][1]:
                # 此循环意在找出同一个 candidate 中包含的多个 money_entity

                true_string, result, offset = self.grid_search(
                    candidate['money_candidate'][bias:])

                if true_string is not None:

                    # rule 1: 判断字符串是否为大概率非货币金额语义
                    if (true_string in self.non_money_string_list) and (not ret_all):
                        bias += offset[1]
                        continue

                    if with_parsing:
                        money_entity_list.append(
                            {'text': true_string,
                             'offset': [candidate['offset'][0] + bias + offset[0],
                                        candidate['offset'][0] + bias + offset[1]],
                             'type': 'money',
                             'detail': result})
                    else:
                        money_entity_list.append(
                            {'text': true_string,
                             'offset': [candidate['offset'][0] + bias + offset[0],
                                        candidate['offset'][0] + bias + offset[1]],
                             'type': 'money'})
                    bias += offset[1]
                else:
                    break

        return money_entity_list

    def _filter(self, money_string):
        # 对字符串进行过滤，某些不符合规则的字符串直接跳过
        # rule 1: 清除边界的标点
        if money_string[0] in '，,' or money_string[-1] in '，,':
            return False

        # rule 2: 字符串为纯数值，则剔除，如 “12”
        if self.money_num_string_pattern.search(money_string):
            return False

        # rule 3: [千万亿]元 后一般不再添加数字再构成角分等信息，如：`359万元2`
        matched_res = self.qian_wan_yi_yuan_exception_check_pattern.search(money_string)
        if matched_res:
            return False

        return True

    def _cleaning(self, money_string):
        # 对字符串进行清洗
        # 清洗空格字符串
        money_string = money_string.replace(' ', '')

        return money_string

    def grid_search(self, money_candidate):
        """ 全面搜索候选货币金额字符串，从长至短，较优 """
        length = len(money_candidate)
        for i in range(length):  # 控制总长，若想控制单字符的串也被返回考察，此时改为 length + 1
            for j in range(i):  # 控制偏移
                try:
                    offset = [j, length - i + j + 1]
                    sub_string = money_candidate[j: offset[1]]

                    # 对字符串进行过滤
                    if not self._filter(sub_string):
                        continue

                    # 对字符串进行清洗
                    clean_sub_string = self._cleaning(sub_string)

                    result = self.parse_money(clean_sub_string)

                    return sub_string, result, offset
                except (ValueError, Exception):
                    continue

        return None, None, None

    def _grid_search_2(self, money_candidate):
        """ 全面搜索候选货币金额字符串，从前至后，从长至短 """
        print(money_candidate)
        length = len(money_candidate)
        for i in range(length - 1):  # 控制起始点
            for j in range(length, i, -1):  # 控制终止点
                try:
                    offset = [i, j]
                    sub_string = money_candidate[i: j]
                    print(sub_string)
                    # 处理假阳性。检查子串，对某些产生歧义的内容进行过滤。
                    # 原因在于，parse_money 会对某些不符合要求的字符串做正确解析.
                    if not MoneyExtractor._filter(sub_string):
                        continue

                    result = self.parse_money(sub_string, strict=True)

                    return sub_string, result, offset
                except (ValueError, Exception):
                    continue

        return None, None, None

    def extract_money_candidates(self, text):
        """ 获取所有的候选货币金额字符串，其中包含了货币金额 """
        idx_count = 0
        text_length = len(text)
        money_candidates_list = list()
        while idx_count < text_length:
            matched_res = self.money_string_pattern.search(text[idx_count:])

            if matched_res is not None:
                tmp_str = matched_res.group()
                if len(tmp_str) > 1:
                    if len(''.join(self.money_kuai_map_jiao_fen_pattern.findall(tmp_str))) == 1 and (
                            '元' not in tmp_str and '钱' not in tmp_str):
                        # 仅有一个 `分毛角块` 字符且无 `元钱` 字符
                        idx_count += matched_res.span()[1]
                        continue

                    money_candidates_list.append(
                        {'money_candidate': matched_res.group(),
                         'offset': [idx_count + matched_res.span()[0],
                                    idx_count + matched_res.span()[1]],
                         'context': text[max(0, idx_count - 5 + matched_res.span()[0]):
                                         min(text_length, idx_count + 5 + matched_res.span()[1])]}
                    )
                idx_count += matched_res.span()[1]
            else:
                break

        return money_candidates_list


if __name__ == '__main__':
    text = '''海航亏损7000万港元出售香港公寓。12月12日，据《香港经济日报》报道，
        海航集团将持有的部分位于香港铜锣湾Yoo Residence大楼中的物业以2.6亿港元的价格出售，相对于去年入手时3.3亿港元的价格来看，
        海航此次出售该物业以公司股权转让的模式转售，亏损了7000多万港元。该物业包括一个顶层复式豪华公寓、1个分层物业及5个车位。
        报道称，两个月前，海航在市场上为该部分物业寻找买家，一度报价达到几千万美元。此外，海航在数月前将去年同时买下的一个地下连1楼的商铺
        以8650万港元的价格出售，买家为香港一家名为荣企的公司，较去年近1.2亿港元入手的价格亏损了约3350万港元。
        以此来看，海航投资Yoo Residence在一年内亏损逾1亿港元。今年以来，海航在香港连续出售其持有的地产类资产。
        2月份，海航集团把香港启德区6565号地块和6562号地块以159.59亿港元卖给了香港恒基兆业地产（00012.HK），股价为二十三块四毛钱。
        3月份，海航又把位于九龙启德第1L区1号地盘新九龙内地段第6564号以63.59亿港元的价格卖给了会德丰（00020.HK）。
        已在5个月前为其融到了50.47亿港元。除了出售地块之外，海航还卖掉了在香港金钟的一处办公室。3月21日，据香港当地媒体《明报》报道，
        海航已于今日出售位于香港金钟力宝中心的一处办公室，成交价为4000多万港元，折合单价为28000港元/平方英尺（折合243300元/平方米），
        较该物业的市场价值38000港元/平方英尺低了近两成。截至目前，海航在香港出售地产类物业已套现至少227亿港元。'''

    extract_money = MoneyExtractor()
    res = extract_money(text, with_parsing=False)
    print(res)

