# -*- coding: utf-8 -*-
from itertools import chain

import jedi

from .console_logging import getLogger

logger = getLogger(__name__)


def format_completion(complete):
    """Returns a tuple of the string that would be visible in
    the completion dialogue and the completion word

    :type complete: jedi.api_classes.Completion
    :rtype: (str, str)
    """
    display, insert = complete.name + '\t' + complete.type, complete.name
    return display, insert


def get_function_parameters(call_signature, with_keywords=True):
    """Return list function parameters, prepared for sublime completion.

    Tuple contains parameter name and default value

    Parameters list excludes: self, *args and **kwargs parameters

    :type call_signature: jedi.api.classes.CallSignature
    :rtype: list of (str, str or None)
    """
    if not call_signature:
        return []

    params = []
    for param in call_signature.params:
        logger.debug('Parameter: {0}'.format((
            type(param._name),
            param._name.get_kind(),
            param._name.string_name
        )))

        if (not with_keywords and
                param.name == '...' or
                '*' in param.description):
            continue

        if not param.name or param.name in ('self', '...'):
            continue

        param_description = param.description.replace('param ', '')
        is_keyword = '=' in param_description

        if is_keyword and with_keywords:
            default_value = param_description.rsplit('=', 1)[1].lstrip()
            params.append((param.name, default_value))
        elif is_keyword and not with_keywords:
            continue
        else:
            params.append((param.name, None))

    return params


class JediFacade:
    """Facade to call Jedi API.


     Action       | Method
    ===============================
     autocomplete | get_autocomplete
    -------------------------------
     goto         | get_goto
    -------------------------------
     usages       | get_usages
    -------------------------------
     funcargs     | get_funcargs
    --------------------------------
    """
    def __init__(
            self,
            env,
            complete_funcargs,
            source,
            line,
            column,
            filename='',
            encoding='utf-8',
            sys_path=None):
        filename = filename or None
        self.script = jedi.Script(
            source=source,
            line=line,
            column=column,
            path=filename,
            encoding=encoding,
            environment=env,
            sys_path=sys_path,
        )
        self.auto_complete_function_params = complete_funcargs

    def get(self, action):
        """Action dispatcher

        TODO: allow pass parameters to make it more dynamic.
        """
        try:
            return getattr(self, 'get_' + action)()
        except Exception:
            logger.exception('`JediFacade.get_{0}` failed'.format(action))

    def get_goto(self):
        """ Jedi "Go To Definition" """
        return self._goto()

    def get_usages(self):
        """ Jedi "Find Usage" """
        return self._usages()

    def get_funcargs(self):
        """Complete callable object parameters with Jedi."""
        complete_all = self.auto_complete_function_params == 'all'
        call_parameters = self._complete_call_assigments(
            with_keywords=complete_all,
            with_values=complete_all
        )
        return ', '.join(p[1] for p in call_parameters)

    def get_autocomplete(self):
        """Jedi completion."""
        args = self._complete_call_assigments(with_keywords=True,
                                              with_values=False)
        completion = self._completion()

        return list(
            chain(args,
                  filter(lambda c: not c[0].endswith('\tparam'), completion))
        )

    def get_docstring(self):
        return self._docstring()

    def get_signature(self):
        return self._docstring(signature=1)

    def _docstring(self, signature=0):
        """ Jedi show doctring or signature

        :rtype: str
        """
        defs = self.script.goto_definitions()
        assert isinstance(defs, list)

        if len(defs) > 0:
            if signature:
                calltip_signature = defs[0].docstring().split('\n\n')[0]
                return calltip_signature.replace('\n', ' ').replace(' = ', '=')
            else:
                return defs[0].docstring()

    def _completion(self):
        """Regular completions.

        :rtype: list of (str, str)
        """
        completions = self.script.completions()
        for complete in completions:
            yield format_completion(complete)

    def _goto(self):
        """Jedi "go to Definitions" functionality.

        :rtype: list of (str, int, int) or None
        """
        definitions = self.script.goto_assignments()
        if all(d.type == 'import' for d in definitions):
            # check if it an import string and if it is get definition
            definitions = self.script.goto_definitions()
        return [(i.module_path, i.line, i.column + 1)
                for i in definitions if not i.in_builtin_module()]

    def _usages(self):
        """Jedi "find usages" functionality.

        :rtype: list of (str, int, int)
        """
        usages = self.script.usages()
        return [(i.module_path, i.line, i.column + 1)
                for i in usages if not i.in_builtin_module()]

    def _complete_call_assigments(
            self,
            with_keywords=True,
            with_values=True):
        """Get function or class parameters and build Sublime Snippet string
        for completion

        :rtype: str
        """
        try:
            call_definition = self.script.call_signatures()[0]
        except IndexError:
            # probably not a function/class call
            return

        parameters = get_function_parameters(call_definition, with_keywords)
        for index, parameter in enumerate(parameters):
            name, value = parameter

            if value is not None and with_values:
                yield (name + '\tparam',
                       '%s=${%d:%s}' % (name, index + 1, value))
            else:
                yield (name + '\tparam',
                       '${%d:%s}' % (index + 1, name))
