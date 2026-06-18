import sys
import time

from ansible import constants as C
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    """Stream a remote file to the standard output of the controller."""

    def run(self, tmp=None, task_vars=None):
        result = super(ActionModule, self).run(tmp, task_vars)

        if task_vars is None:
            task_vars = dict()

        hostname = task_vars.get("inventory_hostname", "unknown")

        log_file = self._task.args.get("file")
        job_id = self._task.args.get("job_id")

        if not log_file or not job_id:
            result["failed"] = True
            result["msg"] = (
                "Missing parameters: 'log_file' and 'job_id' are required."
            )
            return result

        # resolve the async status directory so it matches the original async
        # task
        async_dir = (
            getattr(self._play_context, "async_dir", None)
            or self._task.args.get("_async_dir")
            or task_vars.get("ansible_async_dir")
            or getattr(C, "DEFAULT_ASYNC_DIR", "~/.ansible_async")
        )
        async_dir = self._templar.template(async_dir)

        # track the line cursor so text is not repeated
        current_line = 1

        # stream loop running on the controller
        while True:
            # throttle the loop slightly to protect CPU and bandwidth
            time.sleep(1)

            # check if the asynchronous background task has started and/or
            # finished, call Ansible's built-in async_status module
            # programmatically
            async_res = self._execute_module(
                module_name="ansible.builtin.async_status",
                module_args={"jid": job_id, "_async_dir": async_dir},
                task_vars=task_vars
            )

            if async_res.get("started", 1) == 0:
                # wait for the job to start
                continue

            # fetch only new lines from the remote log file
            # "tail -n +X" prints starting from line X
            tail_cmd = f"tail -n +{current_line} {log_file}"
            tail_res = self._low_level_execute_command(
                tail_cmd, sudoable=True
            )
            stdout = tail_res.get("stdout", "").removeprefix("\r\n")

            if stdout:
                lines = stdout.splitlines()
                for line in lines:
                    # flush immediately to the local terminal screen
                    sys.stdout.write(
                        f"\033[90mlive: [{hostname}] {line}\033[0m\n"
                    )
                sys.stdout.flush()
                current_line += len(lines)

            if async_res.get("finished", 0) == 1:
                # terminate if the job is finished
                break

        result["changed"] = False
        return result
