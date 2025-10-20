Finding available instruments
========================================

Similar to the pyvisa's ResourceManager, RsInstrument can search for available instruments:

.. literalinclude:: Example_FindInstrument.py
   :language: python
   :linenos:


If you have more VISAs installed, the one actually used by default is defined by a secret widget called VISA Conflict Manager. You can force your program to use a VISA of your choice:

.. literalinclude:: Example_FindInstrument_SelectVisa.py
   :language: python
   :linenos:

.. tip::
    We believe our R&S VISA is the best choice for our customers. Couple of reasons why:
    
    - Small footprint
    - Superior VXI-11 and HiSLIP performance
    - Integrated legacy sensors NRP-Zxx support
    - Additional VXI-11 and LXI devices search
    - Available for Windows, Linux, Mac OS