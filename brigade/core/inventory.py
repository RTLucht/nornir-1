from multiprocessing import Manager

from brigade.core import helpers


class Host(object):
    """
    Represents a host.

    Arguments:
        name (str): Name of the host
        group (:obj:`Group`, optional): Group the host belongs to
        **kwargs: Host data

    Attributes:
        name (str): Name of the host
        group (:obj:`Group`): Group the host belongs to
        data (dict): data about the device

    Note:

        You can access the host data in two ways:

        1. Via the ``data`` attribute - In this case you will get access
           **only** to the data that belongs to the host.
           2. Via the host itself as a dict - :obj:`Host` behaves like a
           dict. The difference between accessing data via the ``data`` attribute
           and directly via the host itself is that the latter will also
           return the data if it's available via a parent :obj:`Group`.

        For instance::

            ---
            # hosts
            my_host:
                ip: 1.2.3.4
                group: bma

            ---
            # groups
            bma:
                site: bma
                group: all
            all:
                domain: acme.com

        * ``my_host.data["ip"]`` will return ``1.2.3.4``
        * ``my_host["ip"]`` will return ``1.2.3.4``
        * ``my_host.data["site"]`` will ``fail``
        * ``my_host["site"]`` will return ``bma``
        * ``my_host.data["domain"]`` will ``fail``
        * ``my_host.group.data["domain"]`` will ``fail``
        * ``my_host["domain"]`` will return ``acme.com``
        * ``my_host.group["domain"]`` will return ``acme.com``
        * ``my_host.group.group.data["domain"]`` will return ``acme.com``
    """

    def __init__(self, name, data, group=None, **kwargs):
        self.name = name
        self.group = group
        self.data = data
        self.data["name"] = name

        if isinstance(group, str):
            self.data["group"] = group
        else:
            self.data["group"] = group.name if group else None

        for k, v in kwargs.items():
            self.data[k] = v

    def keys(self):
        """Returns the keys of the attribute ``data`` and of the parent(s) groups."""
        k = list(self.data.keys())
        if self.group:
            k.extend(list(self.group.keys()))
        return k

    def values(self):
        """Returns the values of the attribute ``data`` and of the parent(s) groups."""
        v = list(self.data.values())
        if self.group:
            v.extend(list(self.group.values()))
        return v

    def __getitem__(self, item):
        try:
            return self.data[item]
        except KeyError:
            if self.group:
                return self.group[item]
            raise

    def __setitem__(self, item, value):
        self.data[item] = value

    def __len__(self):
        return len(self.keys())

    def __iter__(self):
        return self.data.__iter__()

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{}: {}".format(self.__class__.__name__, self.name)

    def items(self):
        """
        Returns all the data accessible from a device, including
        the one inherited from parent groups
        """
        if self.group:
            d = self.group.items()
        else:
            d = {}
        return helpers.merge_two_dicts(d, self.data)


class Group(Host):
    """Same as :obj:`Host`"""
    pass


class Inventory(object):
    """
    An inventory contains information about hosts and groups.

    Arguments:
        hosts (dict): keys are hostnames and values are either :obj:`Host` or a dict
            representing the host data.
        groups (dict): keys are group names and values are either :obj:`Group` or a dict
            representing the group data.

    Attributes:
        hosts (dict): keys are hostnames and values are :obj:`Host`.
        groups (dict): keys are group names and the values are :obj:`Group`.
    """

    def __init__(self, hosts, groups=None, data=None, host_data=None):
        manager = Manager() if not data or not host_data else None

        self.data = data if data is not None else manager.dict()

        groups = groups or {}
        self.groups = {}
        for n, g in groups.items():
            if isinstance(g, dict):
                g = Group(name=n, data=manager.dict(), **g)
            self.groups[n] = g

        for g in self.groups.values():
            if g.group is not None and not isinstance(g.group, Group):
                g.group = self.groups[g.group]

        self.hosts = {}
        for n, h in hosts.items():
            if isinstance(h, dict):
                h = Host(name=n, data=manager.dict(), **h)
            if h.group is not None and not isinstance(h.group, Group):
                h.group = self.groups[h.group]
            self.hosts[n] = h

    def filter(self, filter_func=None, **kwargs):
        """
        Returns a new inventory after filtering the hosts by matching the data passed to the
        function. For instance, assume an inventory with::

            ---
            host1:
                site: bma
                role: http
            host2:
                site: cmh
                role: http
            host3:
                site: bma
                role: db

        * ``my_inventory.filter(site="bma")`` will result in ``host1`` and ``host3``
        * ``my_inventory.filter(site="bma", role="db")`` will result in ``host3`` only

        Arguments:
            filter_func (callable): if filter_func is passed it will be called against each
              device. If the call returns ``True`` the device will be kept in the inventory
        """
        if filter_func:
            filtered = {n: h for n, h in self.hosts.items()
                        if filter_func(h, **kwargs)}
        else:
            filtered = {n: h for n, h in self.hosts.items()
                        if all(h[k] == v for k, v in kwargs.items())}
        return Inventory(hosts=filtered, groups=self.groups, data=self.data)
