function [ macs ] = loadmacs( )
%LOADMACS Load mac address list and ap names from macs file
%   Detailed explanation goes here
    
    file = '../../macs';
    macs = tdfread(file);
     
end

