from zhinst.toolkit import Session
session = Session("localhost")
# print(list(session.child_nodes(recursive=True, leavesonly=True)))
# copyright = session.about.copyright()
# print(copyright)
session.devices.visible()

device = session.connect_device("DEV1004")