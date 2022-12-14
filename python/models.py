# -*- coding: utf-8 -*-
"""
Created on Sun Jan 16 18:58:09 2022

@author: wangz
"""
import time 

import torch
import torch.nn.functional as F
from torch_geometric.utils import add_self_loops
from layers import BiGCNConv,BiGCNConv_og,BiGCNConv1, indBiGCNConv,indBiGCNConv1,indBiGCNConv3, BiSAGEConv, BiGraphConv
from Function import BinActive, BinActive0,BinLinear

import torch.nn.functional as F
import torch
from torch.autograd import Variable
import torch.nn as nn
from torch.nn.quantized import QFunctional
import pandas as pd


class BernoulliDropout(nn.Module):
    def __init__(self, p=0.0):
        super(BernoulliDropout, self).__init__()
        self.p = torch.nn.Parameter(torch.ones((1,))*p, requires_grad=False)
        if self.p < 1:
            self.multiplier = torch.nn.Parameter(
                torch.ones((1,))/(1.0 - self.p), requires_grad=False)
        else:
            self.multiplier = torch.nn.Parameter(
                torch.ones((1,))*0.0, requires_grad=False)

        self.mul_mask = torch.nn.quantized.FloatFunctional()
        self.mul_scalar = torch.nn.quantized.FloatFunctional()
        
    def forward(self, x):
        if self.p <= 0.0:
            return x
        mask_ = None
        if len(x.shape) <= 3:
            if x.is_cuda:
                mask_ = torch.cuda.FloatTensor(x.shape,device=1).bernoulli_(1.-self.p)
            else:
                mask_ = torch.FloatTensor(x.shape).bernoulli_(1.-self.p)
        else:
            
            if x.is_cuda:
                mask_ = torch.cuda.FloatTensor(x.shape[:2]).bernoulli_(
                    1.-self.p)
            else:
                mask_ = torch.FloatTensor(x.shape[:2]).bernoulli_(
                    1.-self.p)
        if isinstance(self.mul_mask, QFunctional):
            scale = self.mul_mask.scale
            zero_point = self.mul_mask.zero_point
            mask_ = torch.quantize_per_tensor(
                mask_, scale, zero_point, dtype=torch.quint8)
        #if len(x.shape) > 2:
            
         #   mask_ = mask_.view(
          #      mask_.shape[0], mask_.shape[1],1,1).expand(-1,-1, x.shape[1],x.shape[2])
       
        x = self.mul_mask.mul(x,mask_)
        x = self.mul_scalar.mul_scalar(x, self.multiplier.item())
        return x

    def extra_repr(self):
        return 'p={}, quant={}'.format(
            self.p.item(), isinstance(
                self.mul_mask, QFunctional)
        )



class BiGCN_og(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels, layers, dropout, print_log=True):
        super(BiGCN_og, self).__init__()

        if print_log:
            print("Create a {:d}-layered Bi-GCN.".format(layers))

        self.layers = layers
        self.dropout = dropout
        self.bn1 = torch.nn.BatchNorm1d(in_channels, affine=False)

        convs = []
        for i in range(self.layers):
            in_dim = hidden_channels if i > 0 else in_channels
            out_dim = hidden_channels if i < self.layers - 1 else out_channels
            if print_log:
                print("Layer {:d}, in_dim {:d}, out_dim {:d}".format(i, in_dim, out_dim))
            convs.append(BiGCNConv_og(in_dim, out_dim, cached=True, bi=True))
        self.convs = torch.nn.ModuleList(convs)

        self.reset_parameters()

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

    def forward(self, data):
        x, edge_index = data.x, data.edge_index

        x = self.bn1(x)

        for i, conv in enumerate(self.convs):
            x = BinActive()(x)
            x = BernoulliDropout(0.5)(x)
                          
            x = conv(x, edge_index)
            #if i != self.layers - 1:   
               

        return F.log_softmax(x, dim=1)
     
    




        
        
class BiGCN(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels,adj, out_channels,layers, dropout, print_log=True):
        super(BiGCN, self).__init__()

        if print_log:
            print("Create a {:d}-layered Bi-GCN.".format(layers))

        self.layers = layers
        self.adj=adj
        self.dropout = dropout
        self.bn1 = torch.nn.BatchNorm1d(in_channels, affine=False)

        convs = []
        convs1=[]
        for i in range(self.layers):
        
            if i==0 :
              in_dim = in_channels  
            if i==1:  
              in_dim =hidden_channels 
            if 1<i< self.layers:
              in_dim= 32
            
            if i==0 :
              out_dim = hidden_channels  
            if 0 < i < self.layers-1:  
              out_dim =32 
            if i== self.layers-1:
              out_dim= out_channels
            if print_log:
                print("Layer {:d}, in_dim {:d}, out_dim {:d}".format(i, in_dim, out_dim))
            convs.append(BiGCNConv(in_dim, out_dim, cached=True, bi=True))
            convs1.append(BiGCNConv1(in_dim, out_dim, cached=True, bi=True))
            
     
        self.convs = torch.nn.ModuleList(convs)
        self.convs1 = torch.nn.ModuleList(convs1)

        self.reset_parameters()

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

    def forward(self, data):
       
        x, edge_index = data.x, data.edge_index 
        #print(edge_index.shape)  
        #print(edge_index)     
        #begin6 = time.time()
        x = self.bn1(x)
        #end6 = time.time()
        #print(end6-begin6)
        
        begin4=time.time()
        for i, conv in enumerate(self.convs):
            
            
            x = BinActive()(x1) 
            #print(x)
            #x = F.dropout(x, p=self.dropout, training=self.training)
            x = conv(x,self.adj)
            if i < self.layers - 1:                 
                x = BernoulliDropout(0.5)(x)
                #print(x)
            
                        
        end4 = time.time()
       # print(end4-begin4)

            #print(x.shape)
            #print(edge_index.shape)
        x.cpu() 
        return F.log_softmax(x, dim=1)
                                                                                                                                  
    def inference(self, data):               
         x=data.x
         x = self.bn1(x)
         
        
         for i, conv1 in enumerate(self.convs1):
                       
            x = BinActive()(x) 
             
            x = conv1(x, adj1)
                                  
            if i != self.layers-1:    
              begin3=time.time()  
              x = BernoulliDropout(0.5)(x)
              end3=time.time()
              #print(end3-begin3)
                    
         begin1=time.time()                                                  
         x.cpu()  
         end1=time.time()               
         
         #print(end1-begin1)
         
         return F.log_softmax(x, dim=1)



class BiGCN_layerspar(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels,layers, num_layer,dropout,dropout2,binarize1,binarize2, print_log=True):
        super(BiGCN_layerspar, self).__init__()

        if print_log:
            print("Create a {:d}-layered Bi-GCN.".format(layers))
        
        self.dropout = dropout
        self.dropout2 = dropout2
        self.layers = layers
        self.num_layer = num_layer
        self.bn1 = torch.nn.BatchNorm1d(in_channels, affine=False)
        self.binarize1 =binarize1
        
        convs = []
        convs1 = []
        for i in range(self.layers):
        
            if i==0 :
              in_dim = in_channels  
            if i==1:  
              in_dim =hidden_channels 
            if 1<i< self.layers:
              in_dim=256           
            if i ==0  :
              out_dim = hidden_channels  
            if  0< i <self.layers-1:  
              out_dim = 256
            if  i == self.layers-1:
              out_dim= out_channels
            if print_log:
                print("Layer {:d}, in_dim {:d}, out_dim {:d}".format(i, in_dim, out_dim))
            convs.append(BiGCNConv(in_dim, out_dim, cached=True, bi=self.binarize1))
            convs1.append(BiGCNConv1(in_dim, out_dim, cached=True, bi=self.binarize1))
     
        self.convs = torch.nn.ModuleList(convs)
        self.convs1 = torch.nn.ModuleList(convs1)

        self.reset_parameters()

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

    def forward(self, data):       
        x, edge_index = data.x, data.edge_index 
        
        x = self.bn1(x)
       
        begin1=time.time()               
        for i, conv in enumerate(self.convs):           
            #begin4 = time.time()
            
            if self.binarize1 :
                 x = BinActive()(x) 
            
            if self.dropout2 == 'input' :    
              if   i != 0 :                 
                x = BernoulliDropout(self.dropout)(x)
                                                      
            x = conv(x, edge_index)            
            x = self.convs1[i](x, edge_index)
            
            if self.dropout2 == 'output' :
              if   i != self.layers -1 :                 
               x = BernoulliDropout(self.dropout)(x)
           
        x.cpu()              
        return F.log_softmax(x, dim=1)
        
        
        
    def inference1(self, data,num_layer,binarize2): 
              
        x, edge_index = data.x, data.edge_index  
        x = self.bn1(x)
              
        for i, conv in enumerate(self.convs):
            #print(i)
            if i == num_layer:
                  break
            if self.binarize1 :
               x = BinActive()(x) 
               
 
            if self.dropout2 == 'input' :    
                if   i != 0 :                 
                 x = BernoulliDropout(self.dropout)(x)
  
            
                                     
            x = conv(x, edge_index)
            
           
            if binarize2 :
               if i!= self.layers-1: 
                 x = BinActive0()(x) 
       
            x = self.convs1[i](x, edge_index) 
          
            if self.dropout2 == 'output' : 
               if   i != self.layers -1:                 
                  x = BernoulliDropout(self.dropout)(x) 
                                         
   
            
        x.cpu()             
        return x
        
    def inference2(self, data,num_layer,edge_index,binarize2 ): 
        x = data
                
        for i, conv in enumerate(self.convs):
            if i > num_layer-1:
            
               if self.binarize1 :
                   x = BinActive()(x) 
              
               
               begin7=time.time()
                                              
               
               if self.dropout2 == 'input' :    
                if   i != 0 :                 
                 x = BernoulliDropout(self.dropout)(x)
               
                 
                              
               x = conv(x, edge_index)
               
               if binarize2 :
                 if  i != self.layers-1:    
                   x = BinActive0()(x) 
                          
               x = self.convs1[i](x, edge_index)
              
               if self.dropout2 == 'output' : 
                if   i != self.layers -1: 
                                          
                 x = BernoulliDropout(self.dropout)(x)  
                                                                               
                 
               end7=time.time()            
           
            
        begin_write=time.time()
        x.cpu() 
        end_write=time.time()
    
              
        return F.log_softmax(x, dim=1)
            
       

class NeighborSamplingGCN(torch.nn.Module):
    def __init__(self, model: str, in_channels, hidden_channels, out_channels, binarize, dropout=0.):
        super(NeighborSamplingGCN, self).__init__()

        assert model in ['indGCN', 'GraphSAGE'], 'Only indGCN and GraphSAGE are available.'
        GNNConv = indBiGCNConv3 if model == 'indGCN' else BiSAGEConv

        self.num_layers = 2
        self.model = model
        self.binarize = binarize
        self.dropout = dropout

        self.convs = torch.nn.ModuleList()
        self.convs.append(GNNConv(in_channels, hidden_channels, binarize=binarize))
        self.convs.append(GNNConv(hidden_channels, out_channels, binarize=binarize))
        self.reset_parameters()

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

    def forward(self, x, adjs):

        for i, (edge_index, _, size) in enumerate(adjs):
            x_target = x[:size[1]]
            if(self.binarize):
                x = x - x.mean(dim=1, keepdim=True)
                x = x / (x.std(dim=1, keepdim=True) + 0.0001)
                x = BinActive()(x)

                x_target = x_target - x_target.mean(dim=1, keepdim=True)
                x_target = x_target / (x_target.std(dim=1, keepdim=True) + 0.0001)
                x_target = BinActive()(x_target)
            # if self.model == 'GraphSAGE':
            #     edge_index, _ = add_self_loops(edge_index, num_nodes=x[0].size(0))
            x = self.convs[i]((x, x_target), edge_index)
            if i != self.num_layers - 1:
                x = F.relu(x)
                x = F.dropout(x, p=self.dropout, training=self.training)
        return x.log_softmax(dim=-1)

    def inference(self, x_all, subgraph_loader, device):
        for i in range(self.num_layers):
            xs = []
            for batch_size, n_id, adj in subgraph_loader:
                edge_index, _, size = adj.to(device)
                x = x_all[n_id].to(device)
                x_target = x[:size[1]]
                if self.binarize:
                    # bn x
                    x = x - x.mean(dim=1, keepdim=True)
                    x = x / (x.std(dim=1, keepdim=True) + 0.0001)
                    x = BinActive()(x)

                    # bn x_target
                    x_target = x_target - x_target.mean(dim=1, keepdim=True)
                    x_target = x_target / (x_target.std(dim=1, keepdim=True) + 0.0001)
                    x_target = BinActive()(x_target)
                x = self.convs[i]((x, x_target), edge_index)
                if i != self.num_layers - 1:
                    x = F.relu(x)
                    x = BernoulliDropout(0.5)(x)
                xs.append(x.cpu())

            x_all = torch.cat(xs, dim=0)
        return x_all

# indGCN and GraphSAGE
class NeighborSamplingGCN1(torch.nn.Module):
    def __init__(self, model: str, in_channels, hidden_channels, out_channels, binarize, dropout=0.):
        super(NeighborSamplingGCN1, self).__init__()

        assert model in ['indGCN', 'GraphSAGE'], 'Only indGCN and GraphSAGE are available.'
        GNNConv = indBiGCNConv if model == 'indGCN' else BiSAGEConv

        self.num_layers = 2
        self.model = model
        self.binarize = binarize
        self.dropout = dropout
        self.convs1 = torch.nn.ModuleList()
        self.convs2 = torch.nn.ModuleList()
        
        self.convs1.append(indBiGCNConv1(in_channels, hidden_channels,binarize=Ture))
        self.convs1.append(indBiGCNConv1(hidden_channels, out_channels,binarize=Ture))
        self.convs2.append(indBiGCNConv(in_channels, hidden_channels,binarize=Ture))       
        self.convs2.append(indBiGCNConv(hidden_channels, out_channels,binarize=Ture))
        self.reset_parameters()

    def reset_parameters(self):
        for conv in self.convs1:
            conv.reset_parameters()

    def forward(self, x, adjs):

        for i, (edge_index, _, size) in enumerate(adjs):
           
            x_target = x[:size[1]]
            
            x = x - x.mean(dim=0, keepdim=True)
            x = x / (x.std(dim=0, keepdim=True) + 0.0001)
            x = BinActive()(x)
            
                   
            #x_target = x_target - x_target.mean(dim=0, keepdim=True)
            #x_target = x_target / (x_target.std(dim=0, keepdim=True) + 0.0001)
            #x_target = BinActive()(x_target)
            if i != 0:
                   x = BernoulliDropout(0.5)(x)
           
            
            x = self.convs1[i](x,edge_index)
            if i != self.num_layers - 1:
              x = BinActive0()(x)
            x = self.convs2[i]((x,x_target),edge_index)
            if i != self.num_layers - 1:
                x = F.relu(x)
                #x = BernoulliDropout(0.5)(x)
               
        return x.log_softmax(dim=-1)

    def inference(self, x_all, subgraph_loader, device, return_lat=False):
        begin_time = time.time()
        load_time = 0.0
        bin_active_time = 0.0
        conv_time = 0.0
        cc=0
        torch.no_grad()
        #torch.set_num_interop_threads(72)
        #torch.set_num_threads(72)
        #print ("Number of Inter Thred:", torch.get_num_interop_threads())
        #print ("Number of Intra Thread:", torch.get_num_threads())
        
        for i in range(self.num_layers):
            xs = []
            #print ("layer no.:", i)
            
            
            for batch_size, n_id, adj in subgraph_loader:
                #load_begin_time = time.time()
                layer_begin_time = time.time()
                #print(n_id)
                
                
                edge_index, _, size = adj.to(device)
                #if i==0:
                x = x_all[n_id].to(device)
                #else:
                 #  x=x
                
                x_target = x[:size[1]]
               
              
                x = x - x.mean(dim=0, keepdim=True)
                x = x / (x.std(dim=0, keepdim=True) + 0.0001)
                x = BinActive()(x)

                 bn x_target
                x_target = x_target - x_target.mean(dim=0, keepdim=True)
                x_target = x_target / (x_target.std(dim=0, keepdim=True) + 0.0001)
                x_target = BinActive()(x_target)
                
                
                
                if i != 0:
                   #x=torch.stack((x,x,x,x,x,x,x,x,x,x),dim=0
                
                   x = BernoulliDropout(0.5)(x)
                  
                  

                conv_begin_time = time.time()
                
                begin1=time.time()
                x = self.convs1[i](x, edge_index)
                if i != self.num_layers - 1:
              
                  x = BinActive0()(x)
                  
        
                x = self.convs2[i](x, edge_index) 
                end1=time.time()
                #print(begin1-end1)
                
                        
                if i != self.num_layers - 1:
                    
                    x = F.relu(x)                     
            
                    #x = BernoulliDropout(0.5)(x)
                    
       
                xs.append(x.cpu())
                
                                                                         
            x_all =  torch.cat(xs, dim=1)
        
                  
        return  x_all


class SAINT(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels, dropout, binarize):
        super(SAINT, self).__init__()
        self.dropout = dropout
        self.binarize = binarize
        self.conv1 = BiGraphConv(in_channels, hidden_channels, binarize=self.binarize)
        self.conv2 = BiGraphConv(hidden_channels, hidden_channels, binarize=self.binarize)
        # if self.binarize:
        #     self.lin = BinLinear(2 * hidden_channels, out_channels)
        # else:
        self.lin = torch.nn.Linear(2 * hidden_channels, out_channels)

    def set_aggr(self, aggr):
        self.conv1.aggr = aggr
        self.conv2.aggr = aggr

    def reset_parameters(self):
        self.conv1.reset_parameters()
        self.conv2.reset_parameters()
        self.lin.reset_parameters()

    def forward(self, x0, edge_index, edge_weight=None):
        if self.binarize:
            x0 = x0 - x0.mean(dim=1, keepdim=True)
            x0 = x0 / (x0.std(dim=1, keepdim=True) + 0.0001)
            x0 = BinActive()(x0)

        x1 = self.conv1(x0, edge_index, edge_weight)
        if not self.binarize:
            x1 = F.relu(x1)
        x1 = F.dropout(x1, p=self.dropout, training=self.training)

        if self.binarize:
            x2 = BinActive()(x1)
        else:
            x2 = x1
        x2 = self.conv2(x2, edge_index, edge_weight)
        if not self.binarize:
            x2 = F.relu(x2)
        x2 = F.dropout(x2, p=self.dropout, training=self.training)

        x = torch.cat([x1, x2], dim=-1)
        x = self.lin(x)
        return x.log_softmax(dim=-1)
