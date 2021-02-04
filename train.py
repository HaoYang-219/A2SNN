import os

import torch
import torch.nn as nn
from torch.optim import Adam

from attacks.fgsm import fgsm
from attacks.pgd import pgd
from metrics import accuracy
from utils import normalize_cifar10, normalize_cifar100, normalize_generic


def train_vanilla(model, train_loader, test_loader, args, device='cpu'):
    optimizer = Adam(model.parameters(), lr=args['lr'], weight_decay=args['wd'])
    loss_func = nn.CrossEntropyLoss()
    if args['dataset'] == 'cifar10':
        norm_func = normalize_cifar10
    elif args['dataset'] == 'cifar100':
        norm_func = normalize_cifar100
    elif args['dataset'] == 'svhn':
        norm_func = normalize_generic
    else:
        norm_func = None
    best_test_acc = -1.
    for epoch in range(args['num_epochs']):
        for data, target in train_loader:
            data = data.to(device)
            target = target.to(device)
            model.train()
            if norm_func is not None:
                data = norm_func(data)
            logits = model(data)
            optimizer.zero_grad()
            loss = loss_func(logits, target)
            loss.backward()
            optimizer.step()
        train_acc = accuracy(model, train_loader, device=device, norm=norm_func)
        test_acc = accuracy(model, test_loader, device=device, norm=norm_func)
        if test_acc > best_test_acc:
            best_test_acc = test_acc
            torch.save(model.state_dict(), os.path.join(args['output_path']['models'], 'ckpt_best.pt'))
            print('Best accuracy achieved on epoch {}.'.format(epoch + 1))
        print('Epoch {:03}, Train acc: {:.3f}, Test acc: {:.3f}'.format(epoch + 1, train_acc, test_acc))


def train_stochastic(model, train_loader, test_loader, args, device='cpu'):
    if args['var_type'] == 'isotropic':
        trainable_noise_params = {'params': model.base.sigma, 'lr': args['lr'], 'weight_decay': args['wd']}
    elif args['var_type'] == 'anisotropic':
        trainable_noise_params = {'params': model.base.L, 'lr': args['lr'], 'weight_decay': args['wd']}
    optimizer = Adam([
        {'params': model.base.gen.parameters(), 'lr': args['lr']},
        {'params': model.base.fc1.parameters(), 'lr': args['lr']},
        trainable_noise_params,
        {'params': model.proto.parameters(), 'lr': args['lr'], 'weight_decay': args['wd']}
    ])
    # Uncomment for the "train model and noise separately" ablation. But first train a model with disable_noise=True.
    # model.freeze_model_params()
    loss_func = nn.CrossEntropyLoss()
    if args['dataset'] == 'cifar10':
        norm_func = normalize_cifar10
    elif args['dataset'] == 'cifar100':
        norm_func = normalize_cifar100
    elif args['dataset'] == 'svhn':
        norm_func = normalize_generic
    elif args['dataset'] in ('mnist', 'fmnist'):
        norm_func = None
    best_test_acc = -1.
    for epoch in range(args['num_epochs']):
        for data, target in train_loader:
            data = data.to(device)
            target = target.to(device)
            model.train()
            if norm_func is not None:
                data = norm_func(data)
            logits = model(data)
            optimizer.zero_grad()
            if args['reg_type'] == 'wca':
                if args['var_type'] == 'isotropic':
                    wca = (model.proto.weight @ model.sigma.diag() @ model.proto.weight.T).diagonal().sum()
                elif args['var_type'] == 'anisotropic':
                    wca = (model.proto.weight @ model.sigma @ model.proto.weight.T).diagonal().sum()
                loss = loss_func(logits, target) - torch.log(wca)
            elif args['reg_type'] == 'max_entropy':
                me = model.base.dist.entropy().mean()
                loss = loss_func(logits, target) - torch.log(me)
            elif args['reg_type'] == 'wca+max_entropy':
                if args['var_type'] == 'isotropic':
                    wca = (model.proto.weight @ model.sigma.diag() @ model.proto.weight.T).diagonal().sum()
                elif args['var_type'] == 'anisotropic':
                    wca = (model.proto.weight @ model.sigma @ model.proto.weight.T).diagonal().sum()
                me = model.base.dist.entropy().mean()
                loss = loss_func(logits, target) - torch.log(wca) - torch.log(me)
            loss.backward()
            optimizer.step()
            if args['var_type'] == 'anisotropic':
                with torch.no_grad():
                    model.base.L.data = model.base.L.data.tril()
        train_acc = accuracy(model, train_loader, device=device, norm=norm_func)
        test_acc = accuracy(model, test_loader, device=device, norm=norm_func)
        print('Epoch {:03}, Train acc: {:.3f}, Test acc: {:.3f}'.format(epoch + 1, train_acc, test_acc))
        if test_acc > best_test_acc:
            best_test_acc = test_acc
            model.save(os.path.join(args['output_path']['models'], 'ckpt_best'))
            print('Best accuracy achieved on epoch {}.'.format(epoch + 1))


def train_stochastic_adversarial(model, train_loader, test_loader, args, device='cpu'):
    if args['var_type'] == 'isotropic':
        trainable_noise_params = {'params': model.base.sigma, 'lr': args['lr'], 'weight_decay': args['wd']}
    elif args['var_type'] == 'anisotropic':
        trainable_noise_params = {'params': model.base.L, 'lr': args['lr'], 'weight_decay': args['wd']}
    optimizer = Adam([
        {'params': model.base.gen.parameters(), 'lr': args['lr']},
        {'params': model.base.fc1.parameters(), 'lr': args['lr']},
        trainable_noise_params,
        {'params': model.proto.parameters(), 'lr': args['lr'], 'weight_decay': args['wd']}
    ])
    # Uncomment for the "train model and noise separately" ablation. But first train a model with disable_noise=True.
    # model.freeze_model_params()
    loss_func = nn.CrossEntropyLoss()
    if args['dataset'] == 'cifar10':
        norm_func = normalize_cifar10
    elif args['dataset'] == 'cifar100':
        norm_func = normalize_cifar100
    elif args['dataset'] == 'svhn':
        norm_func = normalize_generic
    elif args['dataset'] in ('mnist', 'fmnist'):
        norm_func = None
    if args['attack'] == 'fgsm':
        attack_func = fgsm
    elif args['attack'] == 'pgd':
        attack_func = pgd
    best_test_acc = -1.
    for epoch in range(args['num_epochs']):
        for data, target in train_loader:
            data = data.to(device)
            target = target.to(device)
            perturbed_data = attack_func(model, data, target, epsilon=args['epsilon']).to(device)
            model.train()
            if norm_func is not None:
                data = norm_func(data)
                perturbed_data = norm_func(perturbed_data)
            logits = model(data)
            adv_logits = model(perturbed_data)
            optimizer.zero_grad()
            clean_loss = loss_func(logits, target)
            adv_loss = loss_func(adv_logits, target)
            if args['reg_type'] == 'wca':
                if args['var_type'] == 'isotropic':
                    wca = (model.proto.weight @ model.sigma.diag() @ model.proto.weight.T).diagonal().sum()
                elif args['var_type'] == 'anisotropic':
                    wca = (model.proto.weight @ model.sigma @ model.proto.weight.T).diagonal().sum()
                loss = args['w_ct'] * clean_loss + args['w_at'] * adv_loss - torch.log(wca)
            elif args['reg_type'] == 'max_entropy':
                me = model.base.dist.entropy().mean()
                loss = args['w_ct'] * clean_loss + args['w_at'] * adv_loss - torch.log(me)
            elif args['reg_type'] == 'wca+max_entropy':
                if args['var_type'] == 'isotropic':
                    wca = (model.proto.weight @ model.sigma.diag() @ model.proto.weight.T).diagonal().sum()
                elif args['var_type'] == 'anisotropic':
                    wca = (model.proto.weight @ model.sigma @ model.proto.weight.T).diagonal().sum()
                me = model.base.dist.entropy().mean()
                loss = args['w_ct'] * clean_loss + args['w_at'] * adv_loss - torch.log(wca) - torch.log(me)
            loss.backward()
            optimizer.step()
            if args['var_type'] == 'anisotropic':
                with torch.no_grad():
                    model.base.L.data = model.base.L.data.tril()
        train_acc = accuracy(model, train_loader, device=device, norm=norm_func)
        test_acc = accuracy(model, test_loader, device=device, norm=norm_func)
        print('Epoch {:03}, Train acc: {:.3f}, Test acc: {:.3f}'.format(epoch + 1, train_acc, test_acc))
        if test_acc > best_test_acc:
            best_test_acc = test_acc
            model.save(os.path.join(args['output_path']['models'], 'ckpt_best'))
            print('Best accuracy achieved on epoch {}.'.format(epoch + 1))
