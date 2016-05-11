from __future__ import print_function
import re
import time
import unittest
from testcases import AutopilotPatternTest, WaitTimeoutError, debug

class WorkshopStackTest(AutopilotPatternTest):

    project_name = 'workshop'

    @debug
    def test_scaleup_scaledown(self):
        """
        Given the workshop stack, when we scale up a service then new
        instances should appear in the Nginx virtualhost config. When
        we scale down a service the instances should be removed from
        the Nginx virtualhost config.
        """
        # make sure both services register with nginx
        self.settle('sales', 1)
        self.settle('customers', 1)

        # test scale-up
        self.scale_and_check('sales', 3, '3000')

        # test scale-down
        self.scale_and_check('sales', 2, '3000')

    def scale_and_check(self, service, count, port):
        """
        Run `docker-compose scale <service>=<count>` on the service,
        wait for it to settle, and then verify that Nginx has the correct
        IPs for the servers in its upstream block.
        """
        self.docker_compose_scale(service, count)
        self.settle(service, count)
        servers = self.get_upstream_blocks(service)
        servers.sort()

        ips = self.get_service_ips(service)[1]
        expected = ['{}:{}'.format(ip, port) for ip in ips]
        expected.sort()
        self.assertEqual(servers, expected,
                         'Upstream blocks {} did not match actual IPs {}'
                         .format(servers, expected))


    def settle(self, service, count):
        """
        Wait for `count` instance of `service` to read as 'Up' and
        then wait for them to show up in the Nginx virtualhost config.
        """
        nodes = self.wait_for_service(service, count)
        if len(nodes) < count:
            self.fail('Failed to scale {} to {} instances'
                      .format(service, count))
        timeout = 15
        while timeout > 0:
            servers = self.get_upstream_blocks(service)
            if len(servers) == count:
                break
            time.sleep(1)
            timeout -= 1
        else:
            raise WaitTimeoutError('Timed out waiting for {} server '
                                   'in nginx upstream'.format(service))

    def get_upstream_blocks(self, service):
        """
        Parse the Nginx config file to get the server address:port
        blocks for the upstream block for `service`
        """
        exit_code, config, _ = self.docker_compose_exec(
            'nginx_1',
            'cat /etc/nginx/nginx.conf')
        if exit_code:
            self.fail('Got non-zero exit code from docker exec')

        regex = re.compile('upstream {} \{{.*?\}}'.format(service),
                           re.MULTILINE|re.DOTALL)
        matches = regex.search(config)
        if not matches:
            return []
        return [l.strip('server; ') for l in matches.group(0).split('\n')
                if 'server' in l]


if __name__ == "__main__":
    unittest.main()