# Copyright (C) 2025 Vantage Compute Corporation
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
"""Template engine for deployment configurations."""

import io
import shlex
from typing import List

from ruamel.yaml import YAML
from vantage_sdk.cluster.schema import VantageClusterContext
from vantage_sdk.exceptions import ConfigurationError

from .constants import (
    SLURM_JWKS_URL_SUFFIX,
    SLURMRESTD_DEFAULTS,
    VANTAGE_AGENT_SNAP_CLOUDFRONT_BASE_URL,
    VANTAGE_AGENT_SNAP_NAME,
    generate_slurm_conf,
    generate_slurmdbd_conf,
    generate_sssd_conf,
)


class CloudInitTemplate:
    """Template engine for cloud-init configurations using proper YAML structure."""

    def __init__(self):
        """Initialize YAML processor with proper settings."""
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.width = 4096

    def generate_multipass_config(self, context: VantageClusterContext) -> str:
        """Generate cloud-init configuration for multipass instances."""
        try:
            # Build the cloud-config as a proper Python dictionary
            sssd_conf = generate_sssd_conf(
                org_id=context.org_id,
                ldap_uri=context.ldap_url,
                sssd_binder_password=context.sssd_binder_password,
            )

            cloud_config = {
                "write_files": [
                    {
                        "path": "/etc/sssd/sssd.conf",
                        "content": sssd_conf,
                        "owner": "root:root",
                        "permissions": "0600",
                    },
                    {
                        "path": "/etc/ssh/sshd_config.d/vantage-sshd.conf",
                        "content": (
                            "PubkeyAuthentication yes\n"
                            "AuthorizedKeysCommand /usr/bin/sss_ssh_authorizedkeys\n"
                            "AuthorizedKeysCommandUser root\n"
                            "PasswordAuthentication no\n"
                        ),
                        "owner": "root:root",
                        "permissions": "0600",
                    },
                    {
                        "path": "/etc/nsswitch.conf",
                        "content": (
                            "passwd:         files systemd sss\n"
                            "group:          files systemd sss\n"
                            "shadow:         files systemd sss\n"
                            "gshadow:        files systemd\n"
                            "\n"
                            "hosts:          files dns\n"
                            "networks:       files\n"
                            "\n"
                            "protocols:      db files\n"
                            "services:       db files sss\n"
                            "ethers:         db files\n"
                            "rpc:            db files\n"
                            "\n"
                            "netgroup:       nis sss\n"
                            "automount:  sss\n"
                            "\n"
                            "sudoers: files sss\n"
                        ),
                        "owner": "root:root",
                        "permissions": "0644",
                    },
                    {
                        "path": "/etc/systemd/logind.conf.d/keep-user-sessions.conf",
                        "content": (
                            "[Login]\n"
                            "KillUserProcesses=no\n"
                            "UserStopDelaySec=300\n"
                        ),
                        "owner": "root:root",
                        "permissions": "0644",
                    },
                    {
                        "path": "/etc/slurm/slurm.conf",
                        "content": generate_slurm_conf(context.cluster_name),
                        "owner": "slurm:slurm",
                        "permissions": "0644",
                    },
                    {
                        "path": "/etc/slurm/slurmdbd.conf",
                        "content": generate_slurmdbd_conf(),
                        "owner": "slurm:slurm",
                        "permissions": "0600",
                    },
                    {
                        "path": "/etc/default/slurmrestd",
                        "content": SLURMRESTD_DEFAULTS,
                        "owner": "root:root",
                        "permissions": "0644",
                    },
                ],
                "runcmd": self._build_runcmd_list(context),
            }

            # Convert to YAML string
            stream = io.StringIO()
            stream.write("#cloud-config\n")
            self.yaml.dump(cloud_config, stream)
            return stream.getvalue()

        except (AttributeError, KeyError, TypeError) as e:
            raise ConfigurationError(f"Failed to generate multipass cloud-init config: {e}")

    def _build_runcmd_list(self, context: VantageClusterContext) -> List[str]:
        """Build the runcmd list for cloud-init."""
        commands = [
            f"""bash <<'SH'
set -euo pipefail

bash /opt/slurm/view/assets/slurm_assets/slurm_install.sh --full-init --cluster-name {context.cluster_name}

# auth/slurm reads slurm.key from StateSaveLocation, not /etc/slurm
if [[ -f /etc/slurm/slurm.key && -d /var/lib/slurm/checkpoint ]]; then
    cp /etc/slurm/slurm.key /var/lib/slurm/checkpoint/slurm.key
    chmod 600 /var/lib/slurm/checkpoint/slurm.key
    chown slurm:slurm /var/lib/slurm/checkpoint/slurm.key
fi
SH""",
            self._rewrite_slurm_configs_after_full_init(context),
            # SSSD config is already written via write_files; set up PAM and enable services
            """bash <<'SH'
set -euo pipefail

apt-get update -qq && apt-get install -y -qq libsss-sudo
pam-auth-update --enable sss
pam-auth-update --enable mkhomedir
systemctl restart ssh
systemctl --now enable sssd.service
systemctl restart systemd-logind
SH""",
        ]

        commands.extend(self._generate_slurm_jwks_config(context))
        commands.append(self._generate_slurm_config_resolve_command())
        commands.extend(self._start_slurm_services())

        # Agent configuration commands
        commands.extend(self._install_vantage_agent(context))
        commands.extend(self._generate_vantage_agent_cloud_init_snap_config(context))

        return commands

    def _rewrite_slurm_configs_after_full_init(self, context: VantageClusterContext) -> str:
        """Re-apply Slurm config files after full-init, which can overwrite them."""
        slurm_conf = generate_slurm_conf(context.cluster_name).rstrip("\n")
        slurmdbd_conf = generate_slurmdbd_conf().rstrip("\n")

        return f"""bash <<'SH'
set -euo pipefail

cat >/etc/slurm/slurm.conf <<'EOF_SLURM_CONF'
{slurm_conf}
EOF_SLURM_CONF

cat >/etc/slurm/slurmdbd.conf <<'EOF_SLURMDBD_CONF'
{slurmdbd_conf}
EOF_SLURMDBD_CONF

chown slurm:slurm /etc/slurm/slurm.conf /etc/slurm/slurmdbd.conf
chmod 644 /etc/slurm/slurm.conf
chmod 600 /etc/slurm/slurmdbd.conf
SH"""

    def _generate_slurm_jwks_config(self, context: VantageClusterContext) -> List[str]:
        """Fetch Keycloak JWKS and write the Slurm auth file."""
        jwks_url = shlex.quote(context.oidc_base_url.rstrip("/") + SLURM_JWKS_URL_SUFFIX)

        return [
            f"""bash <<'SH'
set -euo pipefail

JWKS_URL={jwks_url} python3 - <<'PY'
import json
import os
from pathlib import Path
import urllib.request

jwks_url = os.environ["JWKS_URL"]
with urllib.request.urlopen(jwks_url, timeout=30) as response:
    jwks_json = json.loads(response.read().decode("utf-8"))

jwks_path = Path("/etc/slurm/jwks.json")
jwks_path.parent.mkdir(parents=True, exist_ok=True)
jwks_path.write_text(json.dumps(jwks_json, indent=2, sort_keys=True) + "\\n")
PY
SH""",
        ]

    @staticmethod
    def _generate_slurm_config_resolve_command() -> str:
        """Detect hardware on-VM and substitute @PLACEHOLDER@ tokens in slurm configs."""
        return """bash <<'SH'
set -euo pipefail

HEADNODE_HOSTNAME=$(hostname)
HEADNODE_ADDRESS=$(hostname -I | awk '{print $1}')

cpu_info=$(lscpu -J | jq)
CPUs=$(echo "$cpu_info" | jq -r '.lscpu | .[] | select(.field == "CPU(s):") | .data')
THREADS_PER_CORE=$(echo "$cpu_info" | jq -r '.lscpu | .[] | select(.field == "Thread(s) per core:") | .data')
CORES_PER_SOCKET=$(echo "$cpu_info" | jq -r '.lscpu | .[] | select(.field == "Core(s) per socket:") | .data')
SOCKETS=$(echo "$cpu_info" | jq -r '.lscpu | .[] | select(.field == "Socket(s):") | .data')
REAL_MEMORY=$(free -m | grep -oP '\\d+' | head -n 1)

for conf in /etc/slurm/slurm.conf /etc/slurm/slurmdbd.conf; do
    sed -i \
        -e "s|@HEADNODE_HOSTNAME@|$HEADNODE_HOSTNAME|g" \
        -e "s|@HEADNODE_ADDRESS@|$HEADNODE_ADDRESS|g" \
        -e "s|@CPUs@|$CPUs|g" \
        -e "s|@THREADS_PER_CORE@|$THREADS_PER_CORE|g" \
        -e "s|@CORES_PER_SOCKET@|$CORES_PER_SOCKET|g" \
        -e "s|@SOCKETS@|$SOCKETS|g" \
        -e "s|@REAL_MEMORY@|$REAL_MEMORY|g" \
        "$conf"
done

chown slurm:slurm /etc/slurm/slurm.conf /etc/slurm/slurmdbd.conf
chmod 644 /etc/slurm/slurm.conf
chmod 600 /etc/slurm/slurmdbd.conf
SH"""

    def _start_slurm_services(self) -> List[str]:
        """Start Slurm services after configuration files are present."""
        return [
            "systemctl enable slurmdbd",
            "systemctl restart slurmdbd",
            "systemctl enable slurmctld",
            "systemctl restart slurmctld",
            "systemctl enable slurmd",
            "systemctl restart slurmd",
            "systemctl enable slurmrestd",
            "systemctl restart slurmrestd",
        ]

    def _install_vantage_agent(self, context: VantageClusterContext) -> List[str]:
        """Generate commands to install vantage-agent."""
        return [
            f"""bash <<'SH'
set -euo pipefail

SNAP_ARCH=$(dpkg --print-architecture)
SNAP_NAME={shlex.quote(VANTAGE_AGENT_SNAP_NAME)}
SNAP_BASE_URL={shlex.quote(VANTAGE_AGENT_SNAP_CLOUDFRONT_BASE_URL)}
SNAP_URL="$SNAP_BASE_URL/$SNAP_ARCH/latest/$SNAP_NAME.snap"
OIDC_TOKEN_URL={shlex.quote(context.oidc_base_url + '/realms/vantage/protocol/openid-connect/token')}

AUTH_TOKEN=$(
    curl -fsSL -X POST "$OIDC_TOKEN_URL" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "grant_type=client_credentials" \
        --data-urlencode "client_id={shlex.quote(context.client_id)}" \
        --data-urlencode "client_secret={shlex.quote(context.client_secret)}" |
    python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])'
)

curl -fsSL \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    "$SNAP_URL" \
    -o /tmp/${{SNAP_NAME}}.snap

snap install --classic --dangerous /tmp/${{SNAP_NAME}}.snap
SH""",
        ]

    def _generate_vantage_agent_cloud_init_snap_config(
        self, context: VantageClusterContext
    ) -> List[str]:
        """Generate vantage-agent specific cloud-init snap configuration."""
        return [
            f"snap set vantage-agent vantage-url={context.base_api_url}",
            f"snap set vantage-agent cluster-client-id={context.client_id}",
            f"snap set vantage-agent cluster-client-secret={context.client_secret}",
            f"snap set vantage-agent slurm-accounts-reconciler.ldap-bind-password={context.sssd_binder_password}",
        ]

    def _generate_jupyterhub_config(self, context: VantageClusterContext) -> List[str]:
        """Generate JupyterHub configuration commands."""
        return [
            'echo "JUPYTERHUB_VENV_DIR=/srv/vantage-nfs/vantage-jupyterhub" >> /etc/default/vantage-jupyterhub',
            f'echo "OIDC_CLIENT_ID={context.client_id}" >> /etc/default/vantage-jupyterhub',
            f'echo "OIDC_CLIENT_SECRET={context.client_secret}" >> /etc/default/vantage-jupyterhub',
            f'echo "JUPYTERHUB_TOKEN={context.jupyterhub_token}" >> /etc/default/vantage-jupyterhub',
            f'echo "OIDC_BASE_URL={context.oidc_base_url}" >> /etc/default/vantage-jupyterhub',
            f'echo "TUNNEL_API_URL={context.tunnel_api_url}" >> /etc/default/vantage-jupyterhub',
            f'echo "VANTAGE_API_URL={context.base_api_url}" >> /etc/default/vantage-jupyterhub',
            f'echo "OIDC_DOMAIN={context.oidc_domain}" >> /etc/default/vantage-jupyterhub',
        ]
