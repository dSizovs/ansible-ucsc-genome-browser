"""Collect related Ansible vars into a dictionary.

Given an alias, this module reads all Ansible variables whose name matches the
pattern "alias_*". After that, it writes them to a dictionary.

This is useful to define sets of Ansible variables meant to be used together,
for example sets of environment variables for containerized application
deployments.
"""

import re

from ansible.errors import AnsibleUndefinedVariable
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super(ActionModule, self).run(tmp, task_vars)

        params = {}
        for name in ("alias", "var"):
            param = self._task.args.get(name, None)

            if not param:
                result["failed"] = True
                result["msg"] = f"The '{name}' parameter is required."
                return result

            params[name] = param

        vars_dict = {}

        # pattern to match 'alias_KEY'
        pattern = re.compile(rf"^{params['alias']}_(.+)$")

        for key, value in task_vars.items():
            match = pattern.match(key)
            if match:
                var_key = match.group(1)
                try:
                    vars_dict[var_key] = self._templar.template(value)
                except AnsibleUndefinedVariable:
                    pass

        result["ansible_facts"] = {
            f"{params['var']}": vars_dict
        }
        result["changed"] = False

        return result
