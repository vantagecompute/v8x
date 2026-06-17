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

"""SLURM Multipass Localhost Constants."""

import platform
from pathlib import Path
from textwrap import dedent

APP_NAME = "slurm-multipass"


def generate_sssd_conf(org_id: str, ldap_uri: str, sssd_binder_password: str) -> str:
    """Generate SSSD configuration for LDAP authentication.

    This is the canonical SSSD config template for multipass singlenode
    deployments. Mirrors the structure in vdeployer's vantage_system.py
    but is maintained independently for the CLI path.
    """
    search_base = f"ou={org_id},ou=organizations,dc=vantagecompute,dc=ai"
    user_search_base = f"ou=People,{search_base}"
    bind_dn = f"cn=sssd-binder,ou=ServiceAccounts,{search_base}"
    filter_users = (
        "root,ubuntu,slurm,slurmrestd,daemon,bin,sys,sync,games,man,lp,mail,news,"
        "uucp,proxy,www-data,backup,list,irc,gnats,nobody,systemd-network,"
        "systemd-resolve,messagebus,systemd-timesync,syslog,_apt,tss,uuidd,"
        "tcpdump,landscape,pollinate,sshd,fwupd-refresh"
    )
    filter_groups = (
        "root,ubuntu,slurm,slurmrestd,daemon,bin,sys,adm,tty,disk,lp,mail,news,"
        "uucp,man,proxy,kmem,dialout,fax,voice,cdrom,floppy,tape,sudo,audio,dip,"
        "www-data,backup,operator,list,irc,src,gnats,shadow,utmp,video,sasl,"
        "plugdev,staff,games,users,nogroup,systemd-network,systemd-resolve,"
        "messagebus,systemd-timesync,syslog,_apt,tss,uuidd,tcpdump,landscape,"
        "pollinate,sshd,fwupd-refresh,netdev,lxd"
    )

    return f"""\
[sssd]
config_file_version = 2
services = nss, pam, ssh, sudo
domains  = vantagecompute.ai

[nss]
debug_level = 7
filter_users = {filter_users}
filter_groups = {filter_groups}

[pam]
debug_level = 7
offline_credentials_expiration = 60
reconnection_retries = 3

[domain/vantagecompute.ai]
debug_level = 7

id_provider      = ldap
auth_provider    = ldap
chpass_provider  = ldap
access_provider  = simple
simple_allow_groups = slurm-users
sudo_provider    = ldap

ldap_uri               = {ldap_uri}
ldap_search_base       = {search_base}
ldap_user_search_base  = {user_search_base}
ldap_group_search_base = {search_base}
ldap_sudo_search_base  = ou=Groups,{search_base}

ldap_default_bind_dn      = {bind_dn}
ldap_default_authtok      = {sssd_binder_password}
ldap_default_authtok_type = password

ldap_user_ssh_public_key = sshPublicKey

ldap_user_object_class = posixAccount
ldap_user_name = uid
ldap_user_uid_number = uidNumber
ldap_user_gid_number = gidNumber
ldap_user_home_directory = homeDirectory
ldap_user_shell = loginShell
ldap_user_gecos = cn
ldap_user_fullname = cn

ldap_group_object_class = groupOfNames
ldap_group_member       = member
ldap_group_nesting_level = 0
ldap_group_name         = cn
ldap_group_gid_number   = gidNumber

ldap_user_memberof = memberOf

cache_credentials = true
enumerate = false

entry_cache_timeout = 3600
entry_cache_user_timeout = 3600
entry_cache_group_timeout = 3600
entry_cache_sudo_timeout = 3600
entry_negative_timeout = 30

refresh_expired_interval = 300
ldap_connection_expire_timeout = 900
ldap_network_timeout = 15
ldap_opt_timeout     = 120

ldap_schema = rfc2307bis
"""


CLOUD = "on_prem"

SUBSTRATE = "multipass"

DEFAULT_MULTIPASS_OPERATING_SYSTEM = "rockylinux10"
SUPPORTED_MULTIPASS_OPERATING_SYSTEMS = (
    "rockylinux9",
    "rockylinux10",
    "noble",
    "resolute",
)

VANTAGE_AGENT_SNAP_NAME = "vantage-agent"
# Keep this aligned with the publish workflow path so the CloudFront object stays stable.
VANTAGE_AGENT_SNAP_CLOUDFRONT_BASE_URL = (
    "https://vantage-artifacts.vantagecompute.ai/snaps/vantage-agent-snap"
)

_ARCH_MAP = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
MULTIPASS_ARCH = _ARCH_MAP.get(platform.machine().lower(), "amd64")

MULTIPASS_CLOUD_IMAGE_BASE_URL = (
    f"https://vantage-artifacts.vantagecompute.ai/images/multipass-singlenode/{MULTIPASS_ARCH}"
)


def get_multipass_cloud_image_name(operating_system: str) -> str:
    """Return the cloud image filename for a supported Multipass OS key."""
    if operating_system not in SUPPORTED_MULTIPASS_OPERATING_SYSTEMS:
        supported = ", ".join(SUPPORTED_MULTIPASS_OPERATING_SYSTEMS)
        raise ValueError(
            f"Unsupported Multipass operating system '{operating_system}'. "
            f"Supported values: {supported}."
        )
    return f"multipass-singlenode-{operating_system}-{MULTIPASS_ARCH}.img"


def get_multipass_cloud_image_url(operating_system: str) -> str:
    """Return the remote cloud image URL for a supported Multipass OS key."""
    return f"{MULTIPASS_CLOUD_IMAGE_BASE_URL}/{get_multipass_cloud_image_name(operating_system)}"


def get_multipass_cloud_image_dest(operating_system: str) -> Path:
    """Return the temporary downloaded cloud image path for a supported Multipass OS key."""
    return Path("/tmp") / get_multipass_cloud_image_name(operating_system)


def get_multipass_cloud_image_local(operating_system: str) -> Path:
    """Return the local built cloud image path for a supported Multipass OS key."""
    return (
        Path.home()
        / "multipass-singlenode"
        / "build"
        / get_multipass_cloud_image_name(operating_system)
    )


MULTIPASS_CLOUD_IMAGE_URL = get_multipass_cloud_image_url(DEFAULT_MULTIPASS_OPERATING_SYSTEM)

MULTIPASS_CLOUD_IMAGE_DEST = get_multipass_cloud_image_dest(DEFAULT_MULTIPASS_OPERATING_SYSTEM)

MULTIPASS_CLOUD_IMAGE_LOCAL = get_multipass_cloud_image_local(DEFAULT_MULTIPASS_OPERATING_SYSTEM)

SLURM_JWKS_URL_SUFFIX = "/realms/vantage/protocol/openid-connect/certs"


def generate_slurm_conf(cluster_name: str) -> str:
    """Generate complete slurm.conf with @PLACEHOLDER@ tokens for runtime detection.

    Runtime placeholders (resolved on-VM via hardware detection):
        @HEADNODE_HOSTNAME@  — $(hostname)
        @HEADNODE_ADDRESS@   — primary IPv4
        @CPUs@               — total logical CPUs
        @THREADS_PER_CORE@   — SMT threads per core
        @CORES_PER_SOCKET@   — physical cores per socket
        @SOCKETS@            — CPU sockets
        @REAL_MEMORY@        — total RAM in MB
    """
    return (
        dedent(f"""\
        ClusterName={cluster_name}

        # MCS
        MCSPlugin=mcs/label
        MCSParameters=ondemand,ondemandselect

        SlurmUser=slurm
        SlurmdUser=root
        SlurmdPort=6818
        SlurmctldPort=6817
        SlurmctldHost=@HEADNODE_HOSTNAME@
        SlurmctldAddr=@HEADNODE_ADDRESS@

        # Authentication
        AuthType=auth/slurm
        CredType=cred/slurm
        AuthAltTypes=auth/jwt
        AuthAltParameters=jwt_key=/etc/slurm/jwt_hs256.key,jwks=/etc/slurm/jwks.json,userclaimfield=preferred_username
        AuthInfo=use_client_ids

        SlurmctldPidFile=/run/slurmctld/slurmctld.pid
        SlurmdPidFile=/run/slurmd/slurmd.pid

        SlurmctldLogFile=/var/log/slurm/slurmctld.log
        SlurmdLogFile=/var/log/slurm/slurmd.log

        SlurmdSpoolDir=/var/lib/slurm/slurmd
        StateSaveLocation=/var/lib/slurm/checkpoint

        PluginDir=/opt/slurm/view/lib/slurm

        PlugStackConfig=/etc/slurm/plugstack.conf

        ProctrackType=proctrack/cgroup

        ReturnToService=2
        RebootProgram="/usr/sbin/reboot --reboot"
        MailProg=/usr/bin/mail.mailutils

        # Timers
        SlurmctldTimeout=300
        SlurmdTimeout=60
        InactiveLimit=0
        MinJobAge=86400
        KillWait=30
        Waittime=0

        # Scheduling
        SchedulerType=sched/backfill
        SelectType=select/cons_tres
        SelectTypeParameters=CR_CPU_Memory

        # Logging
        SlurmctldDebug=debug5
        SlurmdDebug=debug5

        # Accounting
        AcctGatherProfileType=acct_gather_profile/influxdb
        AcctGatherNodeFreq=10
        JobAcctGatherType=jobacct_gather/cgroup
        JobAcctGatherFrequency="task=5"

        TaskPlugin="task/cgroup,task/affinity"

        # Slurmdbd
        AccountingStorageType=accounting_storage/slurmdbd
        AccountingStorageHost=@HEADNODE_ADDRESS@
        AccountingStorageUser=slurm
        AccountingStoragePort=6819

        # Node Configurations
        NodeName=@HEADNODE_HOSTNAME@ NodeAddr=@HEADNODE_ADDRESS@ CPUs=@CPUs@ ThreadsPerCore=@THREADS_PER_CORE@ CoresPerSocket=@CORES_PER_SOCKET@ Sockets=@SOCKETS@ RealMemory=@REAL_MEMORY@

        # Partition Configurations
        PartitionName=compute Nodes=@HEADNODE_HOSTNAME@ MaxTime=INFINITE State=UP Default=Yes

        # Nodeset
        NodeSet=compute Feature=compute
    """).strip()
        + "\n"
    )


def generate_slurmdbd_conf() -> str:
    """Generate complete slurmdbd.conf with @PLACEHOLDER@ tokens for runtime detection.

    Runtime placeholders (resolved on-VM):
        @HEADNODE_HOSTNAME@  — $(hostname)
    """
    return (
        dedent("""\
        DbdHost=@HEADNODE_HOSTNAME@
        DbdPort=6819

        AuthType=auth/slurm
        AuthAltTypes=auth/jwt
        AuthAltParameters=jwt_key=/etc/slurm/jwt_hs256.key,jwks=/etc/slurm/jwks.json,userclaimfield=preferred_username

        SlurmUser=slurm
        PluginDir=/opt/slurm/view/lib/slurm
        PidFile=/run/slurmdbd/slurmdbd.pid
        LogFile=/var/log/slurm/slurmdbd.log

        StorageType=accounting_storage/mysql
        StorageHost=127.0.0.1
        StoragePort=3306
        StoragePass=rats
        StorageUser=slurm
        StorageLoc=slurm

        DebugLevel=info
    """).strip()
        + "\n"
    )


SLURMRESTD_DEFAULTS = (
    dedent("""\
    SLURMRESTD_OPTIONS="-s openapi/slurmctld,openapi/slurmdbd"
    SLURM_CONF=/etc/slurm/slurm.conf
""").strip()
    + "\n"
)
