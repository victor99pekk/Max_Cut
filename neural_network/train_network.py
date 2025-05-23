import math
import numpy as np
import torch
import torch.nn.functional as F
from PointerNet import PointerNetwork
from config import *

train_file    = f"data/train_n={n}.csv"
test_file     = f"data/test_n={n}.csv"
embedding_dim = 128
hidden_dim    = 256
batch_size    = 16
num_epochs    = 5 * 10**2
lr            = 0.01
path = "experiments/max_cut/neural_network/saved_models/"
graph_file = "data/graph_n={n}.png"

def load_dataset(filename):
    # Each row has n*n adjacency entries (0/1) + n solution entries (0/1)
    data = np.loadtxt(filename, delimiter=",", dtype=int)
    num_samples, total_dim = data.shape
    # Solve n^2 + n = total_dim for n
    n = int((-1 + math.sqrt(1 + 4 * total_dim)) / 2)
    assert n*n + n == total_dim, f"Bad format: {total_dim} != n^2+n"
    # First n*n cols → adjacency, next n cols → solution
    X = data[:, :n*n].reshape(num_samples, n, n).astype(np.float32)
    Y = data[:, n*n:].astype(int)
    return X, Y, n

def build_target_sequences(Y, n):
    # Build list of index‐sequences: [all ones], EOS, [all zeros]
    eos = n
    seqs = []
    for sol in Y:
        set1 = sorted(i for i, v in enumerate(sol) if v == 1)
        set0 = sorted(i for i, v in enumerate(sol) if v == 0)
        seqs.append(set1 + [eos] + set0)
    return seqs

X_train, Y_train, n_train = load_dataset(train_file)
X_test,  Y_test,  n_test  = load_dataset(test_file)
assert n_train == n_test, "Train/test node count mismatch"
n = n_train

train_seqs = build_target_sequences(Y_train, n)
test_seqs  = build_target_sequences(Y_test,  n)

device   = torch.device("cuda" if torch.cuda.is_available() else "cpu")
X_train_t = torch.tensor(X_train, device=device)  # shape (N_train, n, n)
X_test_t  = torch.tensor(X_test,  device=device)  # shape (N_test,  n, n)

model = PointerNetwork(input_dim=n,
                       embedding_dim=embedding_dim,
                       hidden_dim=hidden_dim).to(device)
optimizer = torch.optim.SGD(model.parameters(), lr=lr)

# load_state = torch.load(path + f"ptr_net_weights_n={n}.pth", map_location="cpu")
# model.load_state_dict(load_state)

# ── Training Loop ────────────────────────────────────────────────────────────────
# model.train()
N_train = X_train_t.size(0)
for epoch in range(1, num_epochs+1):
    model.train()
    perm = torch.randperm(N_train, device=device)
    epoch_loss = 0.0
    for i in range(0, N_train, batch_size):
        idx = perm[i:i+batch_size]
        batch_X = X_train_t[idx]  
        batch_targets = [train_seqs[j] for j in idx.cpu().tolist()]
        optimizer.zero_grad()
        loss = model(batch_X, target_seq=batch_targets)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item() * idx.size(0)
    avg_loss = epoch_loss / N_train
    # if epoch == 1 or epoch % 10 == 0:
    print(f"Epoch {epoch}/{num_epochs} — Avg Loss: {avg_loss:.4f}")

    # ...existing code...
    print(f"Epoch {epoch}/{num_epochs} — Avg Loss: {avg_loss:.4f}")

    # ── Evaluation on Test Set ──────────────────────────────────────────────────────
    model.eval()
    with torch.no_grad():
        N_test = X_test_t.size(0)
        correct = 0
        for i in range(0, N_test, batch_size):
            batch_X = X_test_t[i:i+batch_size]
            outputs = model(batch_X)  # List of length ≤ batch_size of index‐sequences
            for j, out_seq in enumerate(outputs):
                eos_pos = out_seq.index(n) if n in out_seq else len(out_seq)
                chosen  = set(out_seq[:eos_pos])              # nodes in partition 1
                pred    = np.zeros(n, dtype=int)
                pred[list(chosen)] = 1                        # shape (n,)

                # --- ground truth ------------------------------------------------------
                target = Y_test[i + j]                        # numpy array, shape (n,)

                # --- accept either orientation ----------------------------------------
                if np.array_equal(pred, target) or np.array_equal(1 - pred, target):
                    correct += 1
                accuracy = correct / N_test * 100
        print(f"\nTest Accuracy: {correct}/{N_test} = {accuracy:.2f}%")
        torch.save(model.state_dict(), f"neural_network/saved_models/n={n}.pth")
        # print("Saved model in file ptr_net_weights.pth")

    # ── Evaluation on First 200 Training Data Points ────────────────────────────────
    with torch.no_grad():
        N_eval = min(200, X_train_t.size(0))
        correct = 0
        for i in range(0, N_eval, batch_size):
            batch_X = X_train_t[i:i+batch_size]
            outputs = model(batch_X)
            for j, out_seq in enumerate(outputs):
                eos_pos = out_seq.index(n) if n in out_seq else len(out_seq)
                chosen  = set(out_seq[:eos_pos])
                pred    = np.zeros(n, dtype=int)
                pred[list(chosen)] = 1

                target = Y_train[i + j]
                if np.array_equal(pred, target) or np.array_equal(1 - pred, target):
                    correct += 1
                accuracy = correct / N_eval * 100
        print(f"Train Accuracy (first 200): {correct}/{N_eval} = {accuracy:.2f}%")
# ...existing code...