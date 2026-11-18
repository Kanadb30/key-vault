from .builder_frontend import prepare as builder
from .json_dsl_frontend import prepare as elastic
from .nl_frontend import prepare as nl
from .nl_frontend import tokenize as nl_tokens

PREPARE = {"builder": builder, "elastic": elastic, "nl": nl}
LEXERS = {"nl": nl_tokens}
