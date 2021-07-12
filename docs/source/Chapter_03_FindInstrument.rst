3. Finding available instruments
========================================

Like the pyvisa's ResourceManager, RsInstrument can search for available instruments:

.. include:: Example_FindInstrument.py

If you have more VISAs installed, the one actually used by default is defined by a secret widget called VISA Conflict Manager. You can force your program to use a VISA of your choice:

.. include:: Example_FindInstrument_SelectVisa.py

.. tip::
    We believe our R&S VISA is the best choice for our customers. Here are the reasons why:
    
    - Small footprint
    - Superior VXI-11 and HiSLIP performance
    - Integrated legacy sensors NRP-Zxx support
    - Additional VXI-11 and LXI devices search
    - Availability for Windows, Linux, Mac OS