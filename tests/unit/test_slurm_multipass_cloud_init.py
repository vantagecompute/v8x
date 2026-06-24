# Copyright 2025 Vantage Compute Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from types import SimpleNamespace

from ruamel.yaml import YAML

from v8x.apps.on_prem.slurm_multipass.constants import (
    VANTAGE_AGENT_SNAP_CLOUDFRONT_BASE_URL,
)
from v8x.apps.on_prem.slurm_multipass.templates import CloudInitTemplate


def _context() -> SimpleNamespace:
    return SimpleNamespace(
        cluster_name="demo",
        org_id="org-123",
        ldap_url="ldap://ldap.example.com",
        sssd_binder_password="binder-secret",
        base_api_url="https://api.example.com",
        oidc_domain="auth.example.com/realms/vantage",
        client_id="client-id",
        client_secret="client-secret",
        jupyterhub_token="jupyterhub-token",
        oidc_base_url="https://auth.example.com",
        tunnel_api_url="https://tunnel.example.com",
    )


def test_write_files_contain_sssd_config() -> None:
    config = CloudInitTemplate().generate_multipass_config(_context())
    parsed = YAML().load(config)
    write_files = parsed["write_files"]

    sssd_file = next(f for f in write_files if f["path"] == "/etc/sssd/sssd.conf")
    assert sssd_file["permissions"] == "0600"
    assert "services = nss, pam, ssh, sudo" in sssd_file["content"]
    assert "ou=org-123,ou=organizations" in sssd_file["content"]
    assert "ldap://ldap.example.com" in sssd_file["content"]
    assert "binder-secret" in sssd_file["content"]
    assert (
        "ldap_access_filter = (memberOf=cn=slurm-users,ou=Groups,ou=org-123,ou=organizations,dc=vantagecompute,dc=ai)"
        in sssd_file["content"]
    )
    assert "ldap_access_filter = (|" not in sssd_file["content"]
    assert "refresh_expired_interval = 300" in sssd_file["content"]
    assert "ldap_user_memberof = memberOf" in sssd_file["content"]

    nsswitch_file = next(f for f in write_files if f["path"] == "/etc/nsswitch.conf")
    assert "files systemd sss" in nsswitch_file["content"]
    assert "sudoers: files sss" in nsswitch_file["content"]

    logind_file = next(
        f for f in write_files if f["path"] == "/etc/systemd/logind.conf.d/keep-user-sessions.conf"
    )
    assert "UserStopDelaySec=300" in logind_file["content"]

    sshd_file = next(
        f for f in write_files if f["path"] == "/etc/ssh/sshd_config.d/vantage-sshd.conf"
    )
    assert "sss_ssh_authorizedkeys" in sshd_file["content"]


def test_write_files_contain_slurm_configs() -> None:
    config = CloudInitTemplate().generate_multipass_config(_context())
    parsed = YAML().load(config)
    write_files = parsed["write_files"]

    slurm_conf = next(f for f in write_files if f["path"] == "/etc/slurm/slurm.conf")
    assert slurm_conf["permissions"] == "0644"
    assert "ClusterName=demo" in slurm_conf["content"]
    assert (
        "AuthAltParameters=jwt_key=/etc/slurm/jwt_hs256.key,jwks=/etc/slurm/jwks.json,userclaimfield=preferred_username"
        in slurm_conf["content"]
    )
    assert "AuthInfo=use_client_ids" in slurm_conf["content"]
    assert "@HEADNODE_HOSTNAME@" in slurm_conf["content"]
    assert "@CPUs@" in slurm_conf["content"]

    slurmdbd_conf = next(f for f in write_files if f["path"] == "/etc/slurm/slurmdbd.conf")
    assert slurmdbd_conf["permissions"] == "0600"
    assert (
        "AuthAltParameters=jwt_key=/etc/slurm/jwt_hs256.key,jwks=/etc/slurm/jwks.json,userclaimfield=preferred_username"
        in slurmdbd_conf["content"]
    )
    assert "@HEADNODE_HOSTNAME@" in slurmdbd_conf["content"]

    slurmrestd_defaults = next(f for f in write_files if f["path"] == "/etc/default/slurmrestd")
    assert "openapi/slurmctld,openapi/slurmdbd" in slurmrestd_defaults["content"]


def test_multipass_cloud_init_runcmd_structure() -> None:
    config = CloudInitTemplate().generate_multipass_config(_context())
    parsed = YAML().load(config)
    runcmd = parsed["runcmd"]

    assert parsed["package_update"] is False
    assert parsed["package_upgrade"] is False
    assert parsed["packages"] is None

    # runcmd[0]: slurm_install.sh (no SSSD params — config via write_files)
    install_command = runcmd[0]
    assert "slurm_install.sh --full-init --cluster-name demo" in install_command
    assert "--org-id" not in install_command
    assert "--ldap-uri" not in install_command
    assert "--sssd-binder-password" not in install_command

    # runcmd[1]: rewrite Slurm configs after full-init overwrites defaults
    rewrite_configs = runcmd[1]
    assert "cat >/etc/slurm/slurm.conf" in rewrite_configs
    assert (
        "AuthAltParameters=jwt_key=/etc/slurm/jwt_hs256.key,jwks=/etc/slurm/jwks.json,userclaimfield=preferred_username"
        in rewrite_configs
    )

    # runcmd[2]: PAM/SSSD/logind setup
    pam_setup = runcmd[2]
    assert "pam-auth-update --enable sss" in pam_setup
    assert "pam-auth-update --enable mkhomedir" in pam_setup
    assert "authselect select sssd with-mkhomedir --force" in pam_setup
    assert "oddjobd.service" in pam_setup
    assert "sshd.service" in pam_setup
    assert "sssd.service" in pam_setup

    # runcmd[3]: JWKS config
    jwks_command = runcmd[3]
    assert "protocol/openid-connect/certs" in jwks_command
    assert "jwks.json" in jwks_command
    assert "import json" in jwks_command
    assert "json.loads" in jwks_command
    assert "json.dumps" in jwks_command
    assert '+ "\\n")' in jwks_command
    assert '+ "\n")' not in jwks_command

    # runcmd[4]: hardware detection + placeholder substitution
    resolve_command = runcmd[4]
    assert "lscpu -J" in resolve_command
    assert "@HEADNODE_HOSTNAME@" in resolve_command
    assert "@CPUs@" in resolve_command
    assert "slurm.conf" in resolve_command
    assert "slurmdbd.conf" in resolve_command

    # runcmd[5]: database initialization
    database_command = runcmd[5]
    assert 'systemctl enable --now "$database_service"' in database_command
    assert "CREATE USER IF NOT EXISTS 'slurm'@'localhost'" in database_command
    assert "CREATE DATABASE IF NOT EXISTS slurm" in database_command

    # runcmd[6-13]: slurm services
    assert runcmd[6] == "systemctl enable slurmdbd"
    assert runcmd[7] == "systemctl restart slurmdbd"
    assert runcmd[8] == "systemctl enable slurmctld"
    assert runcmd[9] == "systemctl restart slurmctld"
    assert runcmd[10] == "systemctl enable slurmd"
    assert runcmd[11] == "systemctl restart slurmd"
    assert runcmd[12] == "systemctl enable slurmrestd"
    assert runcmd[13] == "systemctl restart slurmrestd"

    # runcmd[14]: vantage-agent install
    agent_command = runcmd[14]
    assert "grant_type=client_credentials" in agent_command
    assert "Authorization: Bearer $AUTH_TOKEN" in agent_command
    assert "snap install --classic --dangerous /tmp/${SNAP_NAME}.snap" in agent_command
    assert f"SNAP_BASE_URL={VANTAGE_AGENT_SNAP_CLOUDFRONT_BASE_URL}" in agent_command
    assert 'SNAP_URL="$SNAP_BASE_URL/$SNAP_ARCH/latest/$SNAP_NAME.snap"' in agent_command
    assert "dpkg --print-architecture" in agent_command
    assert "rpm --eval '%{_arch}'" in agent_command
    assert "SNAP_ARCH=amd64" in agent_command
    assert "SNAP_ARCH=arm64" in agent_command
    assert "snap wait system seed.loaded" in agent_command
    assert not any("jobbergate-agent" in command and "snap set" in command for command in runcmd)
