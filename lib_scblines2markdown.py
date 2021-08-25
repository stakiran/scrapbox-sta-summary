# encoding: utf-8

import re

def dp(msg, flag, caption=''):
    if not flag:
        return
    print(caption + msg)

DP_scb_to_markdown_in_line = False
def dp_scb_to_markdown_in_line(msg):
    dp(msg, DP_scb_to_markdown_in_line, '[step3]')

DP_convert_step2_after_append = False
def dp_convert_step2_after_append(msg):
    dp(msg, DP_convert_step2_after_append, '[step2]')

DP_judge_extra_insertion = False
def dp_judge_extra_insertion(msg):
    dp(msg, DP_judge_extra_insertion)

def dp_all_off():
    DP_scb_to_markdown_in_line = False
    DP_convert_step2_after_append = False
    DP_judge_extra_insertion = False

class MODE:
    INVALID = -1
    NOMODE = 0
    BLANKLINE = 1
    PARAGRAPH = 2
    LIST = 3
    LIST_IN_BLOCK = 4
    START_OF_BLOCK_CODE = 10
    START_OF_BLOCK_TABLE = 11

class LinesContext:
    def __init__(self, lines):
        self._lines = lines

        self._nextline = None
        self._is_first_of_tablecontents = False
        self._is_table_top_blank = False

    def update(self, current_linenumber):
        self._update_nextline(current_linenumber)

    def _update_nextline(self, current_linenumber):
        is_over = current_linenumber>=(len(self._lines)-1)
        if is_over:
            self._nextline = None
            return
        self._nextline = self._lines[current_linenumber+1]

    def enable_first_of_tablecontents(self):
        self._is_first_of_tablecontents = True

    def _disable_first_of_tablecontents(self):
        self._is_first_of_tablecontents = False

    def enable_table_top_blank(self):
        self._is_table_top_blank = True

    def _disable_table_top_blank(self):
        self._is_table_top_blank = False

    @property
    def nextline(self):
        return self._nextline

    def is_first_of_tablecontents(self):
        retval = self._is_first_of_tablecontents
        self._disable_first_of_tablecontents()
        return retval

    def is_table_top_blank(self):
        retval = self._is_table_top_blank
        self._disable_table_top_blank()
        return retval

class InBlockStateUser:
    def __init__(self):
        self._inblockstate = InBlockState()

        # block から抜けた行の検出に必要.
        # 抜けた時の行番号を InBlockState は保持しないので,
        # 利用者(User)の側で保持する必要がある.
        self._is_left_just_now = False

        self._is_left_from_codeblock_just_now = False

    def _clear_just_now_leaving_flags(self):
        self._is_left_just_now = False
        self._is_left_from_codeblock_just_now = False

    def update(self, line, cur_indentdepth, lines_context):
        self._clear_just_now_leaving_flags()

        state = self.state

        if state.is_in_block():
            self._update_case_of_in_block(line, cur_indentdepth, lines_context)
            # block 抜けた直後に次の block に入ることがありえるので
            # (1) 抜けた直後かどうかを判定して,
            if self.is_left_just_now():
                pass
            else:
                return
            # (2) もし抜けた直後だった場合, not in-block 時の処理も行う.
            #     つまり fall throuth する.
        self._update_case_of_not_in_block(line, cur_indentdepth)

    def _update_case_of_not_in_block(self, line, cur_indentdepth):
        state = self.state

        if Moder.is_start_of_code(line):
            state.enter(MODE.START_OF_BLOCK_CODE, cur_indentdepth)
            return

        if Moder.is_start_of_table(line):
            state.enter(MODE.START_OF_BLOCK_TABLE, cur_indentdepth)
            return

    def _update_case_of_in_block(self, line, cur_indentdepth, lines_context):
        state = self.state

        if lines_context.is_table_top_blank():
            # table top blank 問題
            # 
            # - tabletitle と tablecontents の間には step2 の都合上, 空行が入るが,
            #   テーブルは続いているので in block 状態は解除しない
            # - この判定は enable_table_top_blank() の次行で実施する必要があるので
            #   ここで(more deep判定の前で)行う
            return

        is_current_more_deep = cur_indentdepth > state.indentdepth_of_start
        if is_current_more_deep:
            return

        if state.is_in_code_block():
            self._is_left_from_codeblock_just_now = True
        state.leave()
        self._is_left_just_now = True

    @property
    def state(self):
        return self._inblockstate

    def is_left_just_now(self):
        return self._is_left_just_now

    def is_left_from_codeblock_just_now(self):
        return self._is_left_from_codeblock_just_now

class InBlockState:
    def __init__(self):
        self._clear()

    def _clear(self):
        NO_DUPLICATED_VALUE_OF_INDENT_DEPTH = -1

        self._mode = MODE.NOMODE
        self._depth = NO_DUPLICATED_VALUE_OF_INDENT_DEPTH

    def enter(self, mode, indentdepth):
        ''' @param mode MODE.xxx の値(START_OF_XXXX)
        @param indentdepth '''
        already_in_block = self.is_in_block()
        if already_in_block:
            raise RuntimeError('Already in block')

        self._mode = mode
        self._depth = indentdepth

    def leave(self):
        self._clear()

    def is_in_block(self):
        is_not_in_block = self._mode == MODE.NOMODE
        if is_not_in_block:
            return False
        return True

    def is_in_code_block(self):
        is_not_in_block = not self.is_in_block()
        if is_not_in_block:
            return False

        is_matched = self._mode == MODE.START_OF_BLOCK_CODE
        if is_matched:
            return True
        return False

    def is_in_table_block(self):
        is_not_in_block = not self.is_in_block()
        if is_not_in_block:
            return False

        is_matched = self._mode == MODE.START_OF_BLOCK_TABLE
        if is_matched:
            return True
        return False

    @property
    def indentdepth_of_start(self):
        return self._depth

class Moder:
    @classmethod
    def judge_extra_insertion(cls, prev_indentdepth, cur_indentdepth, inblockstate_user, line_for_debug):
        ''' string への挿入を前提としているため, 行指向の場合は適宜解釈し直すこと.
        @return 余分に挿入すべき文字列.
        @retval '' 何も挿入する必要がない.
        
        アルゴリズムがえぐいので Scrapbox のメモも参照のこと. '''

        is_in_list = cur_indentdepth>0
        dp_judge_extra_insertion('indent:{}, B:{}, C:{}, T:{}, L:{} j:{} jc:{}\t{}'.format(
            cur_indentdepth,
            inblockstate_user.state.is_in_block(),
            inblockstate_user.state.is_in_code_block(),
            inblockstate_user.state.is_in_table_block(),
            is_in_list,
            inblockstate_user.is_left_just_now(),
            inblockstate_user.is_left_from_codeblock_just_now(),
            line_for_debug,
        ))

        # returning values
        END_OF_CODE = '```\n'
        IGNORE = ''
        ADD_LINEFEED = '\n'

        # コードブロックの時は空行は要らない(``` の次行にすぐコード内容が続く).
        def start_of_list_or_block(inblockstate_user):
            state = inblockstate_user.state
            if state.is_in_code_block():
                return IGNORE
            return ADD_LINEFEED

        # ★1のケース
        # コードブロックの時は特別な終端を入れる必要がある.
        def end_of_list_or_block(inblockstate_user):
            if inblockstate_user.is_left_from_codeblock_just_now():
                return END_OF_CODE
            return ADD_LINEFEED

        # ★2のケース
        # ダミーリスト挿入はメタでやる.
        def continuous_indent(cur_indentdepth, inblockstate_user):
            is_left_from_codeblock_just_now = inblockstate_user.is_left_from_codeblock_just_now()
            if is_left_from_codeblock_just_now:
                return END_OF_CODE

            is_left_from_block_just_now = inblockstate_user.is_left_just_now()
            if is_left_from_block_just_now:
                return ADD_LINEFEED

            return IGNORE

        # aliases
        p = prev_indentdepth
        c = cur_indentdepth

        # 段落が続いている
        if c==0 and p==0:
            return ADD_LINEFEED

        # list or block が終わった
        if c==0 and p>=1:
            extra_insertion = end_of_list_or_block(inblockstate_user)
            return extra_insertion

        # list or block が始まった
        if c>=1 and p==0:
            extra_insertion = start_of_list_or_block(inblockstate_user)
            return extra_insertion

        # list or block が続いている(インデントは変わらず)
        if c==p:
            return IGNORE

        # list or block が続いている(インデントは深くなった)
        is_more_deepen = c>p
        if is_more_deepen:
            return IGNORE

        # list or block が続いている(インデントは浅くなった)
        extra_insertion = continuous_indent(c, inblockstate_user)
        return extra_insertion

    @classmethod
    def determin_mode(cls, line):
        mode = MODE.INVALID

        if cls.is_start_of_code(line):
            mode = MODE.START_OF_BLOCK_CODE
            return mode
        if cls.is_start_of_table(line):
            mode = MODE.START_OF_BLOCK_TABLE
            return mode

        if cls.is_list(line):
            mode = MODE.LIST
            return mode

        if cls.is_paragraph(line):
            mode = MODE.PARAGRAPH
            return mode

        if cls.is_blankline(line):
            mode = MODE.BLANKLINE
            return mode

        raise RuntimeError('不正なモード. ここに来ることはないはず.\n"{}"'.format(line))

    @classmethod
    def is_blankline(cls, line):
        if len(line) == 0:
            return True
        return False

    @classmethod
    def is_list(cls, line):
        if cls.is_blankline(line):
            return False

        is_firstchar_space = line[:1] == ' '
        is_firstchar_tab = line[:1] == '\t'
        if is_firstchar_space:
            return True
        if is_firstchar_tab:
            return True

        return False

    @classmethod
    def is_paragraph(cls, line):
        if cls.is_blankline(line):
            return False

        if cls.is_start_of_code(line):
            return False
        if cls.is_start_of_table(line):
            return False

        if cls.is_list(line):
            return False

        # 少なくとも空行ではないし,
        # 特殊記法で始まりもしないし,
        # リストでもない.
        #  -> 段落
        #
        # 消去法で決定する.

        return True

    @classmethod
    def is_start_of_code(cls, line):
        if cls.is_blankline(line):
            return False

        stripped_line = line.strip()

        CODE_GRAMMER = 'code:'
        MINIMUM_LENGTH_OF_CODE_GRAMMER = len(CODE_GRAMMER)
        is_too_short = len(stripped_line) <= MINIMUM_LENGTH_OF_CODE_GRAMMER
        if is_too_short:
            return False

        is_matched_prefix = stripped_line.startswith(CODE_GRAMMER)
        if is_matched_prefix:
            return True

        return False

    @classmethod
    def is_start_of_table(cls, line):
        # 不吉な臭い: DRYできるのでは?
        if cls.is_blankline(line):
            return False

        stripped_line = line.strip()

        CODE_TABLE = 'table:'
        MINIMUM_LENGTH_OF_CODE_TABLE = len(CODE_TABLE)
        is_too_short = len(stripped_line) <= MINIMUM_LENGTH_OF_CODE_TABLE
        if is_too_short:
            return False

        is_matched_prefix = stripped_line.startswith(CODE_TABLE)
        if is_matched_prefix:
            return True

        return False

def zenkaku2hankaku(s):
    ret = s
    ret = ret.replace('　', '  ')

    before_strs = 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９'
    after_strs  = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    for i, char in enumerate(before_strs):
        after_c = after_strs[i]
        before_c = char
        ret = ret.replace(before_c, after_c)

    return ret

def fix_filename_to_ghpages_compatible(filename):
    newname = filename
    newname = fix_filename_to_jekyll_compatible(newname)
    newname = fix_filename_to_windows_compatible(newname)

    return newname

def fix_filename_to_jekyll_compatible(filename):
    # jekyll 側で施される謎挙動を吸収する.
    # - [](ここで使われている一部文字.md) が [](勝手に変換されてしまう.html)
    # - jekyll 側でどこで誰が処理してるかもわからないので, 観測ベースで対応していく方針

    # 謎挙動とその対処
    #
    # - ？ が %3F になる
    # - ！ が ! になる
    # - 全角スペースが %E3%80%80 になる
    # - () はそもそも解釈されない(.html に変換されずにスルーされる)
    # etc
    # これは全部 _ に置き換えてしまう.
    #
    # - 全角英数字は全部半角になる
    # これはそのまま半角に合わせる
    # 
    # - _ や . や # で始まるファイル名は認識されない
    # これは jekyll configuration 側の include でワイルドカード使えないせいできりがないので
    # 先頭に - を付与することで回避する

    newname = filename

    invalid_chars = ['(', ')', '（', '）', '！', '？', '　', '～']
    afterstr = '_'
    for invalid_char in invalid_chars:
        newname = newname.replace(invalid_char, afterstr)

    newname = zenkaku2hankaku(newname)

    firstchar = newname[0]
    if firstchar=='.' or firstchar=='#' or firstchar=='_':
        newname = '-'+newname

    return newname

def fix_filename_to_windows_compatible(filename):
    afterstr = '_'
    newname = _fix_filename_to_windows_compatible_minimum(filename, afterstr)

    newname = newname.replace(' ', afterstr)

    return newname

def _fix_filename_to_windows_compatible_minimum(filename, afterstr):
    newname = filename
    newname = newname.replace('\\', afterstr)
    newname = newname.replace('/', afterstr)
    newname = newname.replace(':', afterstr)
    newname = newname.replace('*', afterstr)
    newname = newname.replace('?', afterstr)
    newname = newname.replace('"', afterstr)
    newname = newname.replace('>', afterstr)
    newname = newname.replace('<', afterstr)
    newname = newname.replace('|', afterstr)
    return newname

RE_MARKDOWN_LINK = re.compile(r'\[(.+?)\]\((.+?)\)')
def get_linkee_filename_from_markdown_line(line):
    filenames = []

    def repl(match_object):
        groups = match_object.groups()
        if len(groups)==0:
            return

        is_count_odd = len(groups)%2==1
        if is_count_odd:
            return

        # [text](filename)
        # - textは奇数番目なので無視する
        # - filename として xxx.md のみ想定する
        for i,group in enumerate(groups):
            no = i+1
            is_the_current_number_odd = no%2==1
            if is_the_current_number_odd:
                continue
            filename = group

            is_no_markdown_extension = len(filename)<4
            if is_no_markdown_extension:
                continue
            is_no_markdown_extension = filename[-3:].lower()!='.md'
            if is_no_markdown_extension:
                continue

            filenames.append(filename)
        return

    re.sub(RE_MARKDOWN_LINK, repl, line)
    return filenames

def count_indentdepth(line):
    i = 0
    while line[i:i+1]==' ':
        i += 1
    return i

def convert_step1(scblines):
    lines = scblines
    outlines = []

    # step1: 空行
    # 空行は <br> と \n で置換するのがベストだと事前調査済.

    for line in lines:
        is_not_blankline = not Moder.is_blankline(line)
        if is_not_blankline:
            outlines.append(line)
            continue
        outlines.append('<br>')
        outlines.append('')

    return outlines

def _step2_append_extra_insertion(line, outlines, prev_indentdepth, cur_indentdepth, inblockstate_user):
    line_for_debug = line
    extra_insertion = Moder.judge_extra_insertion(prev_indentdepth, cur_indentdepth, inblockstate_user, line_for_debug)

    is_no_insertion = extra_insertion == ''
    if is_no_insertion:
        return

    is_newline_insertion = extra_insertion == '\n'
    if is_newline_insertion:
        outlines.append('')
        return

    is_endofcode_insertion = extra_insertion == '```\n'
    if is_endofcode_insertion:
        outlines.append('```')
        outlines.append('')
        return

    outlines.append(extra_insertion)

def create_dummylist(cur_indentdepth, using_contents):
    outlines = []
    repcount = cur_indentdepth-1
    for i in range(repcount):
        space_count = i+1
        indent = ' '*space_count
        line = '{}{}'.format(indent, using_contents)
        outlines.append(line)
    return outlines

def convert_step2(step1_converted_lines):
    # step2: インデントの深さに伴う終端処理
    # 終端として必要な文字列(extra insertion)を挿入する.
    # -> \n, コードブロック終点(```) etc

    lines = step1_converted_lines
    outlines = []

    lines_context_dummy = LinesContext(lines)

    inblockstate_user = InBlockStateUser()
    cur_indentdepth = -1
    prev_indentdepth = -1

    is_prev_blankline = False
    is_cur_blankline = False

    # 空行は step1 で処理しているので extra insertion は不要.
    # - 「prevが空行だった」「curが空行」の 2 パターンあるので両方除外する
    # - 除外ルーチンは extra insertion には含まれてないので, メタで(呼び出し元で)やる

    for i,line in enumerate(lines):
        prev_indentdepth = cur_indentdepth
        cur_indentdepth = count_indentdepth(line)
        inblockstate_user.update(line, cur_indentdepth, lines_context_dummy)

        is_prev_blankline = is_cur_blankline
        is_cur_blankline = Moder.is_blankline(line)
        if is_cur_blankline or is_prev_blankline:
            pass
        else:
            _step2_append_extra_insertion(line, outlines, prev_indentdepth, cur_indentdepth, inblockstate_user)

        outlines.append(line)

    # append_extra_insertion で処理できない分の後処理

    # paragraph
    #  list1
    #   list2
    # ★ここに空行を差し込む処理(A)
    #   code:py
    #    print('hello')
    # ```
    #
    #  ... ★ここに左記のようなダミーリストを差し込む処理(B)
    #   list2

    # paragraph
    #  list1
    #   list2
    #   table:xxx
    # ★ここに空行を差し込む処理(C)
    #    a b
    #    c d
    #   list2

    lines = outlines
    outlines = []

    lines_context = LinesContext(lines)
    inblockstate_user = InBlockStateUser()
    cur_indentdepth = -1
    prev_indentdepth = -1
    is_cur_in_block = False
    is_prev_in_block = False
    is_cur_start_of_table = False
    is_prev_start_of_table = False

    for i,line in enumerate(lines):
        prev_indentdepth = cur_indentdepth
        cur_indentdepth = count_indentdepth(line)

        lines_context.update(i)
        inblockstate_user.update(line, cur_indentdepth, lines_context)
        state = inblockstate_user.state

        is_prev_in_block = is_cur_in_block
        is_cur_in_block = state.is_in_block()
        is_cur_in_codeblock = state.is_in_code_block()

        is_prev_in_list = prev_indentdepth > 0

        is_prev_start_of_table = is_cur_start_of_table
        is_cur_start_of_table = Moder.is_start_of_table(line)

        is_cur_in_tableblock = state.is_in_table_block()

        is_cur_start_of_code =  Moder.is_start_of_code(line)

        dp_convert_step2_after_append('(pL, pB, pSoT), (cB, cCB, cTB, cSoT) {} = ({}, {}, {}), ({}, {}, {}, {}) L:{}'.format(
            cur_indentdepth,
            is_prev_in_list,
            is_prev_in_block,
            is_prev_start_of_table,
            is_cur_in_block,
            is_cur_in_codeblock,
            is_cur_in_tableblock,
            is_cur_start_of_table,
            line,
        ))

        # (B)の除外判定用.
        # (B)は tabletitle と tablecontents の間の空行を通る時にも入るので弾く必要がある.
        if state.is_in_table_block() and is_cur_start_of_table:
            dp_convert_step2_after_append('enable table_top_blank about line:{}'.format(
                line,
            ))
            lines_context.enable_table_top_blank()

        # (A)
        # - ただしテーブルの場合は(tabletitleをリストの一行として扱うのが自然なので)差し込まない
        if is_prev_in_list and not is_prev_in_block and is_cur_in_codeblock:
            ADD_LINEFEED = ''
            outlines.append(ADD_LINEFEED)

        # (B)
        # - ただしコード開始時の場合は(次行がリストではなくコード開始になるので)空行が必要
        is_satisfied_B = not is_prev_in_list and not is_cur_in_block and cur_indentdepth>1
        is_satisfied_B_case_of_start_of_table = not is_prev_in_list and cur_indentdepth>1 and is_cur_start_of_table
        is_satisfied_B_case_of_start_of_code = not is_prev_in_list and cur_indentdepth>1 and is_cur_start_of_code
        if is_satisfied_B or is_satisfied_B_case_of_start_of_table:
            DUMMYLIST_CONTENT = '...'
            dummylist = create_dummylist(cur_indentdepth, DUMMYLIST_CONTENT)
            outlines.extend(dummylist)
        elif is_satisfied_B_case_of_start_of_code:
            DUMMYLIST_CONTENT = '...'
            dummylist = create_dummylist(cur_indentdepth, DUMMYLIST_CONTENT)
            outlines.extend(dummylist)
            ADD_LINEFEED = ''
            outlines.append(ADD_LINEFEED)

        # (C)
        if is_prev_in_list and is_prev_start_of_table and is_cur_in_tableblock:
            ADD_LINEFEED = ''
            outlines.append(ADD_LINEFEED)

        outlines.append(line)

    return outlines

def _scb_to_markdown_in_line_about_link_in_decoration(line):
    # link in decoration とは
    # - 装飾文法の中にリンクが存在するケース
    #   例: [- [xxx]xxx[xxx][xxx]xxx[xxx]xxx]yyy[- [xxx]zzz]
    # - ブラケット開始 `[` がネストしているせいで, 正規表現で上手く展開できない
    # - なのでここでは以下の工夫をする
    #   - 「リンクを含む装飾文法」を愚直に検出して,
    #   - 装飾文法部分を先に置換してしまう.
    #
    # Q:先にリンクを置換した後, 装飾文法を置換するのは?
    #   Ans: だめです
    #        リンクを置換しても []() となってしまい, まだブラケット開始がネストしているため.
    #
    # Q:ただのdecorationは置換する?
    #   Ans: しない
    #        なるべく正規表現による置換に任せる方針.

    # [- [a]]
    # 最低でも 7 文字はあるはず
    if len(line)<7:
        return line

    # 状態
    # 定数考えたりインクリメントしたりするのだるいのでランダム文字列にした

    mode_initial = 'v01yRhNu'
    mode_first_leftbracket = 'AgMr3fC6'
    mode_decoration_char = 'SkcB88e3'
    mode_start = 's2XjnzAh'

    mode_link_not_in_decoration_start = 'yuRrkcZE'

    mode_literal_in_decoration_start = 'sfJ6ZD4T'

    mode_second_leftbracket = 'xN9fVtnc'
    mode_start_after_nested_link_found = 'T3WcGMBP'

    # 状態遷移

    surround_startpos = -1
    surround_endpos = -1
    surround_positions = []

    mode = mode_initial
    surrounder = ''
    for i,c in enumerate(line):
        # 無効状態系
        # 受理状態に辿り着かない(辿り着かせない)ための状態.
        # 例: リテラル内は一切合切スルーする(mode_literal_in_decoration_start).
        #
        # スルーすべき範囲を超えたら, 有効状態系に戻る.
        # ----

        if mode==mode_link_not_in_decoration_start:
            if c==']':
                mode = mode_initial
                continue
            continue

        if mode==mode_literal_in_decoration_start:
            if c=='`':
                mode = mode_start
                continue
            continue

        # 有効状態系
        # 受理状態に向けて進んでいく.
        # ----

        if mode==mode_initial:
            surround_startpos = i
            if c=='[':
                mode = mode_first_leftbracket
                continue
            if c=='`':
                mode = mode_literal_in_decoration_start
                continue
            continue

        if mode==mode_first_leftbracket:
            surrounder = ''
            if c=='-':
                mode = mode_decoration_char
                surrounder = '~~'
                continue
            if c=='*':
                mode = mode_decoration_char
                surrounder = '**'
                continue
            mode = mode_link_not_in_decoration_start
            continue

        if mode==mode_decoration_char:
            if c==' ':
                mode = mode_start
                continue
            mode = mode_link_not_in_decoration_start
            continue

        if mode==mode_start:
            if c==']':
                mode = mode_initial
                continue
            if c=='`':
                mode = mode_literal_in_decoration_start
                continue
            if c=='[':
                mode = mode_second_leftbracket
                continue
            continue

        if mode==mode_second_leftbracket:
            if c==']':
                mode = mode_start_after_nested_link_found
                continue
            continue

        if mode==mode_start_after_nested_link_found:
            if c==']':
                surround_endpos = i
                surround_positions.append([surround_startpos, surround_endpos])
                mode = mode_initial
                continue
            if c=='`':
                mode = mode_literal_in_decoration_start
                continue
            if c=='[':
                mode = mode_second_leftbracket
                continue
            continue

    is_not_changed = len(surround_positions) == 0
    if is_not_changed:
        return line

    # 置換処理は最後に一気に行う.
    # - line を list にして 1 文字ずつ注意深く書き換えていくスタイル
    # - surrounder が 2 文字であるという前提
    #   strike が ~~、太字が ** なので今のところ機能している.

    line_by_list = list(line)
    adjuster = 0
    for surround_position in surround_positions:
        s, g = surround_position

        s = s + adjuster

        # sの位置から3文字削除
        for _ in range(3):
            line_by_list.pop(s)

        line_by_list[s:s] = list(surrounder)

        g = g-1
        line_by_list.pop(g)

        line_by_list[g:g] = list(surrounder)

        # 1回処理したら次の start の位置ずれるかと思ったが, ずれなかった(ajuster = 0).
        adjuster = 0

    newline = ''.join(line_by_list)
    return newline

def clear_indent_from_codeblock_line(indentdepth, line):
    # code:xxx が示すコードから,
    # この行が持つインデント数(indentdepth) + 1 個のインデントを取り除く.
    #
    # list0
    #  list1
    #   list2
    #   code:py
    #    print('...')
    #    if True:
    #        print('...')
    # ^^^
    # ここを取り除きたい.
    # ここでは indentdepth=2 なので, 2+1=3 個取り除く必要がある.
    #
    # 既に normalize scb なので, タブは考慮しなくて良い.

    clearning_indent = ' '*(indentdepth+1)
    length_of_clearning_indent = len(clearning_indent)

    is_too_shorten = len(line)<length_of_clearning_indent
    if is_too_shorten:
        return line

    is_matched = line[0:length_of_clearning_indent] == clearning_indent
    is_not_matched = not is_matched
    if is_not_matched:
        return line

    newline = line[length_of_clearning_indent:]
    return newline

def clear_indent_from_tableblock_line(indentdepth, line):
    return clear_indent_from_codeblock_line(indentdepth, line)

RE_CODE_BLOCK_START = re.compile(r'^( )*code\:(.+)$')
def line_to_start_of_codeblock_if_possible(line):
    newline = line
    newline = re.sub(RE_CODE_BLOCK_START, '```\\2', newline)

    # 1  code:xxx     => ```xxx
    # 2  code:xxx.ext => ```ext
    # 3  上記以外

    # 3
    splitted_by_triplebackquote = newline.split('```')
    is_not_start_of_code_line = len(splitted_by_triplebackquote)==1
    if is_not_start_of_code_line:
        return line

    # 1
    MULTI_3BQ_IS_NO_NEED_TO_ASSUME = 1
    prefix, langname_part = newline.split('```', MULTI_3BQ_IS_NO_NEED_TO_ASSUME)
    splitted_by_dot = langname_part.split('.')
    has_not_extension = len(splitted_by_dot)==1
    if has_not_extension:
        return newline

    # 2
    ext = splitted_by_dot[-1]
    newline = '{}```{}'.format(prefix, ext)
    return newline

def tab_delimitor_line_to_markdown_table_line(tab_delimitor_line):
    ls = tab_delimitor_line.split('\t')

    outline = ''
    outline += '|'

    for element in ls:
        outline += ' '
        outline += element
        outline += ' |'

    return outline

def restore_prefix_tabdelimitor(line):
    if len(line)==0:
        return line

    if line[0]!=' ':
        return line

    newline = ''
    converted_count = 0
    for c in line:
        if c==' ':
            newline += '\t'
            converted_count += 1
        else:
            break
    newline += line[converted_count:]
    return newline

def to_markdown_list_grammer(line, cur_indentdepth):
    lstripped_line = line.lstrip()
    markdown_indent = '    '*(cur_indentdepth-1)
    newline = '{}- {}'.format(markdown_indent, lstripped_line)
    return newline

RE_QUOTE = re.compile(r'^( )*\>(.+)')
RE_HASHTAG = re.compile(r'(^| )#(.+?)( |$)')
RE_LINK_ANOTHER_PROJECT = re.compile(r'\[/(.+?)\]')
RE_LINK_ANOTHER_PAGE = re.compile(r'\[([^\-\*/])(.+?)\]([^\(]|$)')
RE_IMAGELINK_GYAZOURL_URL = re.compile(r'\[(https\:\/\/gyazo\.com\/)(.+?)( )http(s){0,1}\:\/\/(.+?)\]')
RE_IMAGELINK_URL_GYAZOURL = re.compile(r'\[http(s){0,1}\:\/\/(.+?)( )(https\:\/\/gyazo\.com\/)(.+?)\]')
RE_LINK_GYAZOURL = re.compile(r'\[(https\:\/\/gyazo\.com\/)(.+?)\]')
RE_LINK_URL_TEXT = re.compile(r'\[http(s){0,1}\:\/\/(.+?)( )(.+?)\]')
RE_LINK_TEXT_URL = re.compile(r'\[(.+?)( )http(s){0,1}\:\/\/(.+?)\]')
RE_LINK_MEDIAURL = re.compile(r'\[(http)(s){0,1}(\:\/\/)(.+?)\]')
RE_LINK_URL_ONLY = re.compile(r'(^| )(http)(s){0,1}(\:\/\/)(.+?)( |$)')
RE_PIPE_IN_LINK_TEXT = re.compile(r'(\[)(.+?)(\|)')
RE_BOLD = re.compile(r'\[\*+( )(.+?)\]')
RE_STRIKE = re.compile(r'\[\-( )(.+?)\]')
def scb_to_markdown_in_line(line, cur_indentdepth, inblockstate_user, lines_context):
    ''' @retval line
    @retval [line, table_separator] これを table starter set と呼ぶ. '''

    # Q:斜体はサポートしない？
    #   Ans: しない.
    #        個人的に使っていないから
    #        実装がだるいから(特に link in dcoration の部分)

    newline = line

    state = inblockstate_user.state
    is_in_list = cur_indentdepth>0
    is_in_block = state.is_in_block()

    # in block
    # ================

    dp_scb_to_markdown_in_line('indent:{}, B:{}, C:{}, T:{}, L:{}\t{}'.format(
        cur_indentdepth,
        is_in_block,
        state.is_in_code_block(),
        state.is_in_table_block(),
        is_in_list,
        line,
    ))

    # コードブロックの中身
    if is_in_block and state.is_in_code_block():
        # code:xxx の開始行も in code block 判定なので, ここで置換処理をする.
        newline = line_to_start_of_codeblock_if_possible(newline)
        # markdown は nested codeblock が存在しないので、コードブロック内のインデントもクリアする.
        newline = clear_indent_from_codeblock_line(state.indentdepth_of_start, newline)
        return newline

    # テーブルの中身
    if is_in_block and state.is_in_table_block():
        # テーブルタイトル
        # - scb 記法の table:xxx にあたる表現は Markdown table には無い
        #   - タイトルを示す行としてつくることにする
        #   - ただし in list 時はリスト記法の反映も必要
        # - table top blank 問題を回避するためのフラグ操作もここでやる.
        #   (line単体ではできないので, メタで(lines contextで)やるしかない)
        if Moder.is_start_of_table(line):
            lines_context.enable_table_top_blank()
            tabletitle = line
            if is_in_list:
                tabletitle = to_markdown_list_grammer(line, cur_indentdepth)
            return tabletitle

        # テーブルタイトルとテーブルコンテンツの間には空行がある.
        # - コンテンツではないので無視する
        # - table separator 挿入タイミングを検出できるのがここしかないので, ここで context に知らせておく
        if Moder.is_blankline(line):
            lines_context.enable_first_of_tablecontents()
            return ''

        # (space-indent)(scb-table-line-with-tab-delimitor)
        # ^^^^^^^^^^^^^^
        # ここは邪魔なので省いてから変換する
        # ただし normalize の影響で空値要素分のtab delimitorもspaceになっているので少々ややこしい
        scb_tableline = clear_indent_from_tableblock_line(state.indentdepth_of_start, newline)
        scb_tableline = restore_prefix_tabdelimitor(scb_tableline)
        newline = tab_delimitor_line_to_markdown_table_line(scb_tableline)

        # table separator を返すべきタイミングは二つある.
        # - is first of tablecontents
        #   - tabletitleとtabletitleに空行がある場合
        #   - 通常はこっち
        # - is table top blank
        #   - 間に空行がない場合
        #   - in list 中のtableはこっちになる
        #
        # @todo テーブルセル内のリンク記法をサポートしたい
        if lines_context.is_first_of_tablecontents() or lines_context.is_table_top_blank():
            pipecount = len(newline.split('|')) - 1
            cellcount = pipecount - 1
            table_separator = '|' + ' - |'*cellcount
            return [newline, table_separator]
        return newline

    # in line
    # ================

    # 最初に処理すべきはリストと引用.
    #
    # 引用から処理する.
    # - リストは引用を含むため, 引用変換時にはリストのインデントを保持する必要がある

    newline = re.sub(RE_QUOTE, '\\1<blockquote>\\2</blockquote>', newline)

    if is_in_list:
        newline = to_markdown_list_grammer(newline, cur_indentdepth)

    # link in decoration
    # - [- [link]] のようにリンクに対して装飾する記法がありうる.
    # - これは開始記号 `[` がネストする関係上, 置換処理が難しいので別関数でやる.
    # - 処理の結果として, ~~[link]~~ のように外側の装飾だけ置換される.

    newline = _scb_to_markdown_in_line_about_link_in_decoration(newline)

    # リンクとメディア(画像と動画)
    #
    # link to another page の正規表現が扱える集合がえぐいので, 以下戦略を取る.
    # - 1: まずは限定的なリンク表記から処理する
    #      画像は gyazo url なら /raw つければアクセスできるので画像記法にしてしまう
    #      その他のメディアは, とりあえずリンクの一種として扱う(記法が本質的にリンクと同じ)
    # - 2: 最後に link to another page を処理する
    #      このとき, 1: で処理した分は markdown link 書式になっているため
    #      ] の直後に ( が来ないパターンを弾くことで 1: を弾ける

    newline = re.sub(RE_HASHTAG, '\\1[#\\2](\\2.md)\\3', newline)

    newline = re.sub(RE_LINK_ANOTHER_PROJECT, '[/\\1](https://scrapbox.io/\\1)', newline)

    newline = re.sub(RE_IMAGELINK_GYAZOURL_URL, '<a href="http\\4://\\5" target="_blank" rel="noopener noreferrer">![](\\1\\2/raw)</a>', newline)
    newline = re.sub(RE_IMAGELINK_URL_GYAZOURL, '<a href="http\\1://\\2" target="_blank" rel="noopener noreferrer">![](\\4\\5/raw)</a>', newline)

    newline = re.sub(RE_LINK_GYAZOURL, '<a href="\\1\\2" target="_blank" rel="noopener noreferrer">![](\\1\\2/raw)</a>', newline)

    newline = re.sub(RE_LINK_URL_TEXT, '[\\4](http\\1://\\2)', newline)
    newline = re.sub(RE_LINK_TEXT_URL, '[\\1](http\\3://\\4)', newline)

    newline = re.sub(RE_LINK_MEDIAURL, '[media](\\1\\2\\3\\4)', newline)

    newline = re.sub(RE_LINK_ANOTHER_PAGE, '[\\1\\2](\\1\\2.md)\\3', newline)

    # Jekyll
    # - url 直書きを <> で囲む
    # - [この中に含まれるパイプを-にする](url)
    #   - 再帰的にn回実行する良い方法が思いつかないので, Amazonのパイプ4個をベースに決め打ち

    newline = re.sub(RE_LINK_URL_ONLY, '\\1<\\2\\3\\4\\5>\\6', newline)
    for _ in range(5):
        newline = re.sub(RE_PIPE_IN_LINK_TEXT, '\\1\\2-', newline)

    # 装飾系単体

    newline = re.sub(RE_BOLD, '**\\2**', newline)
    newline = re.sub(RE_STRIKE, '~~\\2~~', newline)

    return newline

RE_ICON_TO_REMOVE = re.compile(r'\(([^\(\)]+?)\.icon(\*[0-9]+){0,1}(\.md){0,1}\)')
RE_ICON_TO_REPLACE = re.compile(r'\[([^\(\)]+?)(\.icon)(\*[0-9]+){0,1}\]')
def _icon_grammer_to_img_tag(line):
    # icon記法は普通のリンクとして処理されているので, 以下のようになっている.
    #   [sta.icon*3](sta.icon*3.md)
    #   [/icons/Twitter.icon](https://scrapbox.io/icons/Twitter.icon)
    # そのままだと鬱陶しいので, ひとまず :emoji: にしておく.
    #
    # Q:icon*3 のような n-repeat は反映しない?
    #   Ans: しない.
    #        画像の実装を端折ってるのと同じ理由.

    newline = line

    # [sta.icon*3](sta.icon*3.md)
    #             ^^^^^^^^^^^^^^^
    #             まずこっちは要らないので消す
    newline = re.sub(RE_ICON_TO_REMOVE, '', newline)

    # [sta.icon*3]
    #   |
    #   V
    # :sta:
    newline = re.sub(RE_ICON_TO_REPLACE, ':\\1:', newline)

    return newline

def _linkee_filename_to_compatible(line):
    target_filenames = get_linkee_filename_from_markdown_line(line)
    if len(target_filenames)==0:
        return line

    newline = line
    for target_filename in target_filenames:
        compatible_filename = fix_filename_to_ghpages_compatible(target_filename)
        beforestr = '(' + target_filename + ')'
        afterstr = '(' + compatible_filename + ')'
        newline = newline.replace(beforestr, afterstr)
    return newline

def convert_step3(step2_converted_lines):
    # step3: インラインの Scrapbox 記法を Markdown のものに変換

    lines = step2_converted_lines
    outlines = []

    inblockstate_user = InBlockStateUser()
    context = LinesContext(lines)
    cur_indentdepth = -1

    for linenumber,scbline in enumerate(lines):
        cur_indentdepth = count_indentdepth(scbline)
        context.update(linenumber)
        inblockstate_user.update(scbline, cur_indentdepth, context)

        either_line_or_tablestarterset = scb_to_markdown_in_line(scbline, cur_indentdepth, inblockstate_user, context)
        if isinstance(either_line_or_tablestarterset, list):
            markdown_line, table_separator = either_line_or_tablestarterset
        else:
            markdown_line = either_line_or_tablestarterset
            table_separator = ''

        markdown_line = _icon_grammer_to_img_tag(markdown_line)
        markdown_line = _linkee_filename_to_compatible(markdown_line)
        outlines.append(markdown_line)

        if table_separator:
            outlines.append(table_separator)

    return outlines

if __name__ == '__main__':
    pass
